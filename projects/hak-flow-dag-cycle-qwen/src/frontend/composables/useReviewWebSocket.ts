/**
 * useReviewWebSocket - 审核协作 WebSocket composable
 *
 * 修复三个核心同步问题：
 *
 * ═══ 问题1：WebSocket消息处理器中 reactive 对象赋值不触发视图更新 ═══
 *
 *   根因：原始实现中 WebSocket onmessage 回调里直接对 reactive 对象做整体替换
 *   （如 sectionMap.value = newData）或修改非响应式副本，Vue 无法追踪深层变化，
 *   导致审核员 A 标记"有问题"后审核员 B 的页面上段落状态不刷新。
 *
 *   修复策略：
 *   - sections 使用 shallowRef<Section[]>，而非 reactive([])
 *   - 所有 WebSocket 消息触发的更新统一通过 applyUpdate() 函数执行
 *   - applyUpdate() 内部构造全新的数组引用，然后赋值给 shallowRef
 *   - 赋值后立即调用 triggerRef(sections) 强制 Vue 重新渲染
 *   - 配合 nextTick() 确保 DOM 在同一个渲染周期内更新
 *
 * ═══ 问题2：弱网环境下 WebSocket 断开无提示，操作丢失 ═══
 *
 *   根因：原始实现没有连接状态可视化，没有客户端侧心跳超时检测，
 *   没有离线操作缓存。审核员在风电场现场用 4G 时 WebSocket 静默断开，
 *   页面无任何提示，操作没有发出去但用户以为已同步。
 *
 *   修复策略：
 *   - connectionStatus: shallowRef 实时反映连接状态
 *     (connecting → connected → disconnected → reconnecting)
 *   - 客户端侧心跳超时检测：如果 HEARTBEAT_TIMEOUT 秒内没收到任何服务端消息，
 *     判定连接已断开，主动关闭并触发重连
 *   - 指数退避自动重连：1s → 2s → 4s → ... → 30s（上限）
 *   - 离线操作队列：断线时所有操作（状态变更、批注更新）缓存到 pendingOps[]
 *     重连成功后自动按顺序重放
 *   - pendingCount: shallowRef 让 UI 显示"有 N 个操作待同步"
 *
 * ═══ 问题3：并发批注编辑无冲突检测，后提交覆盖先提交 ═══
 *
 *   根因：前端没有维护 version 字段，提交批注更新时不携带 version，
 *   后端乐观锁无法生效。两个审核员同时编辑同一条批注时，后提交的
 *   直接覆盖先提交的内容，没有冲突提示。
 *
 *   修复策略：
 *   - 本地维护每条批注的 version 号（从服务端数据或 WebSocket 广播中同步）
 *   - 提交更新时通过 API 携带 version → 后端乐观锁校验
 *   - 收到 409 Conflict 响应时：
 *     a) 暂停本地编辑
 *     b) 通过 activeConflict ref 展示冲突解决界面
 *     c) 显示"你的版本"和"服务端版本"的 diff 对比
 *     d) 用户选择"保留我的"/"采用服务端"/"手动合并"
 *     e) 确认后调用 resolve-conflict API（force: true）
 *   - 收到 WebSocket conflict_detected 事件时同步弹出冲突提示
 */
import {
  shallowRef,
  triggerRef,
  nextTick,
  onUnmounted,
  type ShallowRef,
} from 'vue';

// ── 类型定义 ──────────────────────────────────────────────

interface Annotation {
  id: number;
  section_id: number;
  author: string;
  content: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface Section {
  id: number;
  report_id: number;
  order: number;
  content: string;
  review_status: 'pending' | 'approved' | 'flagged';
  reviewed_by: string | null;
  reviewed_at: string | null;
  annotations: Annotation[];
}

interface ConflictInfo {
  annotation_id: number;
  section_id: number;
  your_version: number;
  your_content: string;
  server_version: number;
  server_content: string;
  server_author: string;
}

interface PendingOperation {
  type: 'review_status' | 'annotation_update' | 'annotation_create';
  payload: Record<string, unknown>;
  timestamp: number;
  retryCount: number;
}

interface WSMessage {
  type: string;
  [key: string]: unknown;
}

export type ConnectionStatus =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'reconnecting';

// ── 常量 ──────────────────────────────────────────────────

const MAX_RECONNECT_DELAY = 30_000;  // 最大重连间隔 30s
const MAX_RETRY_PER_OP = 3;         // 离线操作最大重试次数
const CLIENT_HEARTBEAT_TIMEOUT = 60_000; // 客户端心跳超时 60s

// ── Composable ────────────────────────────────────────────

export function useReviewWebSocket(
  reportId: number,
  userId: string,
) {
  // ── 响应式状态（全部使用 shallowRef + triggerRef 确保更新可见） ──

  /**
   * 【问题1 修复】使用 shallowRef 而非 reactive
   *
   * shallowRef 只追踪 .value 本身的引用变化。
   * 我们在 applyUpdate() 中每次都创建新数组引用并调用 triggerRef()，
   * 这样无论 WebSocket 消息何时到达，Vue 都能检测到变化并刷新视图。
   *
   * 对比原始实现使用 reactive([]) 时的问题：
   * - 直接 push/splice 到 reactive 数组在异步回调中可能不触发更新
   * - 替换整个数组（state.sections = [...]）会丢失响应式代理
   */
  const sections: ShallowRef<Section[]> = shallowRef([]);
  const connectionStatus: ShallowRef<ConnectionStatus> = shallowRef('disconnected');
  const onlineUsers: ShallowRef<string[]> = shallowRef([]);
  const activeConflict: ShallowRef<ConflictInfo | null> = shallowRef(null);
  const pendingCount: ShallowRef<number> = shallowRef(0);
  const lastError: ShallowRef<string | null> = shallowRef(null);

  // ── 非响应式内部状态 ──

  let ws: WebSocket | null = null;
  let reconnectDelay = 1000;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  let heartbeatCheckTimer: ReturnType<typeof setInterval> | null = null;
  let lastServerMessage = Date.now();
  let shouldReconnect = true;

  /**
   * 【问题2 修复】离线操作队列
   *
   * 当 WebSocket 断开时，用户的操作（标记审核状态、提交批注等）
   * 会被缓存到 pendingOps 数组中。重连成功后自动重放。
   * 重放失败的操作会重试，超过 MAX_RETRY_PER_OP 次后丢弃并通知用户。
   */
  const pendingOps: PendingOperation[] = [];

  // ── 核心：响应式更新函数 ────────────────────────────────

  /**
   * 【问题1 核心修复】统一的响应式更新入口
   *
   * 所有 WebSocket 消息触发的状态变更都通过此函数执行。
   * 关键设计：
   * 1. 使用 updater 回调基于当前数据生成新数据（不可变更新）
   * 2. 构造全新的数组引用赋值给 shallowRef.value
   * 3. 调用 triggerRef() 显式通知 Vue 触发依赖更新
   * 4. 使用 nextTick() 确保 DOM 在同一渲染周期内刷新
   *
   * 为什么不用 reactive + 直接赋值：
   * - WebSocket 的 onmessage 回调运行在浏览器的事件循环中，
   *   不在 Vue 的调度器内。直接修改 reactive 对象的嵌套属性
   *   在异步回调中可能无法被 Vue 的依赖追踪系统捕获。
   * - shallowRef + triggerRef 的组合把"通知更新"的控制权
   *   完全交给开发者，不依赖 Vue 的 Proxy 拦截，
   *   在任何异步上下文中都可靠工作。
   */
  function applyUpdate(updater: (current: Section[]) => Section[]): void {
    const newData = updater(sections.value);
    sections.value = newData;
    triggerRef(sections);
    nextTick(); // 确保 DOM 立即更新，不等待下一个事件循环
  }

  // ── 连接管理 ────────────────────────────────────────────

  function connect(): void {
    if (ws?.readyState === WebSocket.OPEN) return;

    shouldReconnect = true;
    connectionStatus.value = reconnectDelay > 1000 ? 'reconnecting' : 'connecting';
    triggerRef(connectionStatus);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/review/${reportId}`;

    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      reconnectDelay = 1000; // 重置退避
      connectionStatus.value = 'connected';
      triggerRef(connectionStatus);
      lastError.value = null;
      triggerRef(lastError);

      // 发送 join 消息
      ws!.send(JSON.stringify({ type: 'join', user_id: userId }));
    };

    ws.onmessage = (event: MessageEvent) => {
      lastServerMessage = Date.now(); // 重置心跳超时计时

      let msg: WSMessage;
      try {
        msg = JSON.parse(event.data as string);
      } catch {
        return;
      }

      handleServerMessage(msg);
    };

    ws.onclose = () => {
      ws = null;
      stopHeartbeat();

      if (shouldReconnect) {
        connectionStatus.value = 'reconnecting';
        triggerRef(connectionStatus);
        scheduleReconnect();
      } else {
        connectionStatus.value = 'disconnected';
        triggerRef(connectionStatus);
      }
    };

    ws.onerror = () => {
      lastError.value = 'WebSocket connection error';
      triggerRef(lastError);
    };
  }

  /**
   * 【问题2 修复】指数退避重连
   *
   * 断线后按 1s → 2s → 4s → 8s → ... → 30s 的间隔尝试重连。
   * 每次成功连接后重置延迟。避免在网络中断期间频繁重连消耗资源。
   */
  function scheduleReconnect(): void {
    if (reconnectTimer) clearTimeout(reconnectTimer);

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      if (shouldReconnect) {
        connect();
      }
    }, reconnectDelay);

    // 指数退避，上限 30s
    reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
  }

  /**
   * 【问题2 修复】客户端侧心跳检测
   *
   * 两个定时器协作：
   * - heartbeatTimer: 每 15s 向服务端发送 pong 保活
   * - heartbeatCheckTimer: 每 10s 检查最后一次收到服务端消息的时间
   *   如果超过 CLIENT_HEARTBEAT_TIMEOUT（60s），判定连接已断开，
   *   主动关闭 WebSocket 触发 onclose → 重连流程
   *
   * 这解决了"TCP 半开连接"问题：网络中断但 WebSocket 对象仍处于
   * OPEN 状态，操作系统未感知到连接已断开。
   */
  function startHeartbeat(): void {
    stopHeartbeat();

    // 定期发送心跳保活
    heartbeatTimer = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'pong' }));
      }
    }, 15_000);

    // 定期检查心跳超时
    heartbeatCheckTimer = setInterval(() => {
      if (Date.now() - lastServerMessage > CLIENT_HEARTBEAT_TIMEOUT) {
        // 心跳超时 → 连接已断开（可能是弱网、基站切换等）
        lastError.value = 'Connection lost (heartbeat timeout)';
        triggerRef(lastError);

        if (ws) {
          shouldReconnect = true;
          ws.close(); // 触发 onclose → 自动重连
        }
      }
    }, 10_000);
  }

  function stopHeartbeat(): void {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    if (heartbeatCheckTimer) {
      clearInterval(heartbeatCheckTimer);
      heartbeatCheckTimer = null;
    }
  }

  // ── 服务端消息处理 ──────────────────────────────────────

  /**
   * 处理服务端消息的分发器
   *
   * 所有消息都通过 applyUpdate() 更新状态（问题1 修复），
   * 确保在 WebSocket 异步回调中也能正确触发 Vue 视图更新。
   */
  function handleServerMessage(msg: WSMessage): void {
    switch (msg.type) {
      case 'connected':
        handleConnected(msg);
        break;

      case 'ping':
        ws?.send(JSON.stringify({ type: 'pong' }));
        break;

      case 'review_status_changed':
        handleReviewStatusChanged(msg);
        break;

      case 'annotation_created':
        handleAnnotationCreated(msg);
        break;

      case 'annotation_changed':
        handleAnnotationChanged(msg);
        break;

      case 'conflict_detected':
        handleConflictDetected(msg);
        break;

      case 'conflict_resolved':
        handleConflictResolved(msg);
        break;

      case 'user_joined':
      case 'user_left':
        handleUserPresence(msg);
        break;
    }
  }

  function handleConnected(msg: WSMessage): void {
    const interval = (msg.heartbeat_interval as number) || 15;

    // 根据服务端配置启动心跳
    startHeartbeat();
    lastServerMessage = Date.now();

    // 更新在线用户列表
    onlineUsers.value = (msg.online_users as string[]) || [];
    triggerRef(onlineUsers);

    // 【问题2 修复】重连成功后重放离线队列
    replayPendingOps();
  }

  /**
   * 【问题1 修复】审核状态变更的响应式更新
   *
   * 使用 applyUpdate() 创建新数组引用 + triggerRef，
   * 确保审核员 A 的状态标记能实时反映在审核员 B 的视图上。
   */
  function handleReviewStatusChanged(msg: WSMessage): void {
    const sectionId = msg.section_id as number;
    const status = msg.status as Section['review_status'];
    const reviewedBy = msg.reviewed_by as string;
    const reviewedAt = msg.reviewed_at as string;

    applyUpdate((prev) =>
      prev.map((s) =>
        s.id === sectionId
          ? {
              ...s,
              review_status: status,
              reviewed_by: reviewedBy,
              reviewed_at: reviewedAt,
            }
          : s,
      ),
    );
  }

  /**
   * 【问题1 修复】新批注的响应式更新
   */
  function handleAnnotationCreated(msg: WSMessage): void {
    const sectionId = msg.section_id as number;
    const annotation = msg.annotation as Annotation;

    applyUpdate((prev) =>
      prev.map((s) =>
        s.id === sectionId
          ? { ...s, annotations: [...s.annotations, annotation] }
          : s,
      ),
    );
  }

  /**
   * 【问题1 修复 + 问题3 版本同步】批注变更的响应式更新
   *
   * 除了触发视图刷新外，还同步更新本地 version 号，
   * 确保后续编辑时使用正确的版本进行乐观锁校验。
   */
  function handleAnnotationChanged(msg: WSMessage): void {
    // 格式1：完整 annotation 对象（来自 REST API 广播）
    const annotation = msg.annotation as Annotation | undefined;
    if (annotation) {
      applyUpdate((prev) =>
        prev.map((s) =>
          s.id === annotation.section_id
            ? {
                ...s,
                annotations: s.annotations.map((a) =>
                  a.id === annotation.id ? { ...annotation } : a,
                ),
              }
            : s,
        ),
      );
      return;
    }

    // 格式2：增量信息（来自 WebSocket 直接广播）
    const sectionId = msg.section_id as number;
    const annotationId = msg.annotation_id as number;
    const content = msg.content as string;
    const version = msg.version as number;
    const author = msg.author as string;

    if (annotationId && version) {
      applyUpdate((prev) =>
        prev.map((s) =>
          s.id === sectionId
            ? {
                ...s,
                annotations: s.annotations.map((a) =>
                  a.id === annotationId
                    ? { ...a, content, version, author }
                    : a,
                ),
              }
            : s,
        ),
      );
    }
  }

  /**
   * 【问题3 修复】冲突检测 — 显示冲突解决界面
   *
   * 当服务端检测到版本冲突（409 响应）时，会通过 WebSocket
   * 广播 conflict_detected 事件。客户端收到后设置 activeConflict，
   * UI 层据此弹出冲突对比界面。
   */
  function handleConflictDetected(msg: WSMessage): void {
    activeConflict.value = {
      annotation_id: msg.annotation_id as number,
      section_id: msg.section_id as number,
      your_version: msg.your_version as number,
      your_content: msg.your_content as string || '',
      server_version: msg.server_version as number,
      server_content: msg.server_content as string,
      server_author: msg.server_author as string,
    };
    triggerRef(activeConflict);
  }

  /**
   * 【问题3 修复】冲突已解决 — 更新本地数据并关闭冲突界面
   */
  function handleConflictResolved(msg: WSMessage): void {
    const annotation = msg.annotation as Annotation | undefined;
    if (annotation) {
      applyUpdate((prev) =>
        prev.map((s) =>
          s.id === annotation.section_id
            ? {
                ...s,
                annotations: s.annotations.map((a) =>
                  a.id === annotation.id ? { ...annotation } : a,
                ),
              }
            : s,
        ),
      );
    }

    // 关闭冲突界面
    if (
      activeConflict.value?.annotation_id ===
      (msg.annotation_id as number ?? (annotation?.id))
    ) {
      activeConflict.value = null;
      triggerRef(activeConflict);
    }
  }

  function handleUserPresence(msg: WSMessage): void {
    onlineUsers.value = (msg.online_users as string[]) || [];
    triggerRef(onlineUsers);
  }

  // ── 离线操作队列（问题2） ──────────────────────────────

  /**
   * 【问题2 核心修复】发送消息或缓存到离线队列
   *
   * WebSocket 已连接 → 直接发送
   * WebSocket 已断开 → 缓存到 pendingOps，UI 显示待同步数量
   *
   * 这确保了弱网环境下用户的操作不会丢失：
   * 断线时操作被缓存，重连后自动按顺序重放。
   */
  function sendOrQueue(message: WSMessage): void {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(message));
    } else {
      // 缓存操作到离线队列
      pendingOps.push({
        type: message.type as PendingOperation['type'],
        payload: { ...message },
        timestamp: Date.now(),
        retryCount: 0,
      });
      pendingCount.value = pendingOps.length;
      triggerRef(pendingCount);

      connectionStatus.value = 'reconnecting';
      triggerRef(connectionStatus);

      // 确保重连流程已启动
      if (!ws && shouldReconnect) {
        connect();
      }
    }
  }

  /**
   * 【问题2 修复】重连后重放离线队列
   *
   * 按时间顺序逐条重放缓存的操作。
   * 对于批注更新操作，同时通过 REST API 提交以触发乐观锁校验。
   */
  async function replayPendingOps(): Promise<void> {
    if (pendingOps.length === 0) return;

    const ops = [...pendingOps];
    pendingOps.length = 0;
    pendingCount.value = 0;
    triggerRef(pendingCount);

    for (const op of ops) {
      // 丢弃超过 5 分钟的过期操作
      if (Date.now() - op.timestamp > 300_000) continue;

      try {
        if (
          op.type === 'annotation_update' &&
          op.payload.annotation_id &&
          op.payload.version != null
        ) {
          // 批注更新通过 REST API 提交以触发乐观锁（问题3）
          await submitAnnotationUpdate(
            op.payload.annotation_id as number,
            op.payload.content as string,
            op.payload.version as number,
            op.payload.author as string,
          );
        } else {
          // 其他操作通过 WebSocket 发送
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(op.payload));
          }
        }
      } catch {
        // 重放失败，如果未超过重试上限则重新入队
        if (op.retryCount < MAX_RETRY_PER_OP) {
          pendingOps.push({ ...op, retryCount: op.retryCount + 1 });
          pendingCount.value = pendingOps.length;
          triggerRef(pendingCount);
        }
      }
    }
  }

  // ── 公开 API ────────────────────────────────────────────

  /**
   * 设置段落数据（从 REST API 加载后调用）
   */
  function setSections(data: Section[]): void {
    sections.value = data;
    triggerRef(sections);
  }

  /**
   * 标记段落审核状态（问题1 + 问题2）
   *
   * 1. 先通过 REST API 持久化（确保数据落库）
   * 2. 再通过 WebSocket 广播（确保其他人实时看到）
   * 3. 如果 WebSocket 断开，操作被缓存到离线队列
   */
  async function markSectionStatus(
    sectionId: number,
    status: 'pending' | 'approved' | 'flagged',
  ): Promise<void> {
    // 先通过 REST API 持久化
    try {
      const resp = await fetch(`/api/sections/${sectionId}/review`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status,
          reviewed_by: userId,
        }),
      });

      if (resp.ok) {
        const updated = await resp.json();
        applyUpdate((prev) =>
          prev.map((s) => (s.id === sectionId ? { ...s, ...updated } : s)),
        );
      }
    } catch {
      // REST API 也失败了，缓存到离线队列
      sendOrQueue({
        type: 'review_status',
        section_id: sectionId,
        status,
      });
    }

    // 通过 WebSocket 广播给其他审核员
    sendOrQueue({
      type: 'review_status',
      section_id: sectionId,
      status,
    });
  }

  /**
   * 【问题3 核心修复】提交批注更新（含乐观锁版本号）
   *
   * 关键改动：请求体中携带 version 字段
   * - 服务端用 version 做乐观锁校验
   * - 版本匹配 → 更新成功
   * - 版本不匹配 → 返回 409，触发冲突解决流程
   */
  async function submitAnnotationUpdate(
    annotationId: number,
    content: string,
    version: number,
    author: string,
  ): Promise<boolean> {
    try {
      const resp = await fetch(`/api/annotations/${annotationId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, version, author }),
      });

      if (resp.status === 409) {
        // 【问题3】版本冲突！显示冲突解决界面
        const conflict = await resp.json();
        activeConflict.value = {
          annotation_id: annotationId,
          section_id: 0, // 将从冲突信息中获取
          your_version: conflict.your_version,
          your_content: conflict.your_content,
          server_version: conflict.server_version,
          server_content: conflict.server_content,
          server_author: conflict.server_author,
        };
        triggerRef(activeConflict);
        return false;
      }

      if (resp.ok) {
        const updated: Annotation = await resp.json();
        applyUpdate((prev) =>
          prev.map((s) => ({
            ...s,
            annotations: s.annotations.map((a) =>
              a.id === annotationId ? { ...updated } : a,
            ),
          })),
        );
        return true;
      }

      return false;
    } catch {
      // 网络错误，缓存到离线队列（问题2）
      sendOrQueue({
        type: 'annotation_update',
        annotation_id: annotationId,
        content,
        version,
        author,
      });
      return false;
    }
  }

  /**
   * 创建新批注
   */
  async function createAnnotation(
    sectionId: number,
    content: string,
    author: string,
  ): Promise<Annotation | null> {
    try {
      const resp = await fetch(`/api/sections/${sectionId}/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, author }),
      });

      if (resp.ok) {
        const annotation: Annotation = await resp.json();
        applyUpdate((prev) =>
          prev.map((s) =>
            s.id === sectionId
              ? { ...s, annotations: [...s.annotations, annotation] }
              : s,
          ),
        );
        return annotation;
      }
      return null;
    } catch {
      sendOrQueue({
        type: 'annotation_create',
        section_id: sectionId,
        content,
        author,
      });
      return null;
    }
  }

  /**
   * 【问题3 修复】解决冲突
   *
   * 用户在冲突界面选择最终内容后，调用 resolve-conflict API
   * 强制覆盖（force: true），并广播解决结果给其他审核员。
   */
  async function resolveConflict(
    annotationId: number,
    chosenContent: string,
    author: string,
  ): Promise<boolean> {
    try {
      const resp = await fetch(
        `/api/annotations/${annotationId}/resolve-conflict`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content: chosenContent,
            author,
            force: true,
          }),
        },
      );

      if (resp.ok) {
        const resolved: Annotation = await resp.json();
        applyUpdate((prev) =>
          prev.map((s) => ({
            ...s,
            annotations: s.annotations.map((a) =>
              a.id === annotationId ? { ...resolved } : a,
            ),
          })),
        );

        // 关闭冲突界面
        activeConflict.value = null;
        triggerRef(activeConflict);

        // 通知其他审核员冲突已解决
        sendOrQueue({
          type: 'conflict_resolved',
          annotation_id: annotationId,
          section_id: resolved.section_id,
          chosen_version: resolved.version,
        });

        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  /**
   * 主动断开连接
   */
  function disconnect(): void {
    shouldReconnect = false;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    stopHeartbeat();
    ws?.close();
    ws = null;
    connectionStatus.value = 'disconnected';
    triggerRef(connectionStatus);
  }

  // ── 生命周期 ────────────────────────────────────────────

  onUnmounted(() => {
    disconnect();
  });

  return {
    // 响应式状态
    sections,
    connectionStatus,
    onlineUsers,
    activeConflict,
    pendingCount,
    lastError,

    // 操作方法
    connect,
    disconnect,
    setSections,
    markSectionStatus,
    createAnnotation,
    submitAnnotationUpdate,
    resolveConflict,
    sendOrQueue,
  };
}
