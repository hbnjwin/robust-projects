/**
 * 报告审核协作系统 - 前端 Vue 3 应用
 *
 * 修复三个 WebSocket 同步问题:
 *
 * 【问题1】响应式更新:
 *   错误做法: 用 reactive() 创建对象后直接整体赋值 (state = newData)，
 *   这只替换了变量引用，Vue 的 Proxy 追踪不到变化，视图不更新。
 *   正确做法: 使用 ref() 包装，通过 .value 赋值；或对 reactive 对象的
 *   具体属性赋值 (Object.assign / 逐字段修改)，让 Proxy 拦截到 set 操作。
 *
 * 【问题2】断线检测与离线操作:
 *   - 监听 ws.onclose / ws.onerror，立即显示断线横幅
 *   - 指数退避自动重连
 *   - 断线期间将用户操作存入 pendingOps 队列
 *   - 重连成功后自动重发队列中的操作
 *
 * 【问题3】并发冲突检测:
 *   - 本地维护每个批注的 version
 *   - 提交修改时携带 version 字段
 *   - 服务端返回 409 时弹出冲突对话框
 *   - 用户选择保留版本后调用 resolve-conflict API
 */

const { createApp, ref, reactive, onMounted, onUnmounted, nextTick } = Vue;

const app = createApp({
    setup() {
        // ── 核心状态（全部使用 ref 以确保响应式更新）──────────
        const report = ref(null);
        // 【修复问题1】使用 ref 而非 reactive，保证通过 .value 赋值能触发视图更新
        const sections = ref([]);
        const userId = ref('审核员' + String.fromCharCode(65 + Math.floor(Math.random() * 4)));
        const onlineUsers = ref([]);

        // 【修复问题2】连接状态跟踪
        const connectionStatus = ref('disconnected'); // connected | disconnected | reconnecting
        const reconnectAttempts = ref(0);
        const pendingOps = ref([]); // 离线操作队列

        // 批注编辑状态
        const editingAnnotation = ref(null);
        const editContent = ref('');
        const newAnnotationContent = ref({});

        // 【修复问题3】冲突对话框
        const conflict = ref(null);
        const conflictChoice = ref(null);

        let ws = null;
        let reconnectTimer = null;
        let heartbeatTimer = null;
        const reportId = 1;
        const MAX_RECONNECT_DELAY = 30000;
        const BASE_RECONNECT_DELAY = 1000;

        // ── WebSocket 连接管理 ───────────────────────────────

        function connectWebSocket() {
            if (ws && ws.readyState === WebSocket.OPEN) return;

            connectionStatus.value = 'reconnecting';
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws/review/${reportId}`);

            ws.onopen = () => {
                // 发送 join 消息
                ws.send(JSON.stringify({ type: 'join', user_id: userId.value }));
            };

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                handleWsMessage(msg);
            };

            // 【修复问题2】断线检测 — 监听 onclose 和 onerror
            ws.onclose = (event) => {
                connectionStatus.value = 'disconnected';
                clearInterval(heartbeatTimer);
                scheduleReconnect();
            };

            ws.onerror = () => {
                // onerror 之后必然触发 onclose，这里只做标记
                connectionStatus.value = 'disconnected';
            };
        }

        // 【修复问题2】指数退避重连
        function scheduleReconnect() {
            if (reconnectTimer) return;
            reconnectAttempts.value++;
            const delay = Math.min(
                BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts.value - 1),
                MAX_RECONNECT_DELAY
            );
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connectWebSocket();
            }, delay);
        }

        // 【修复问题2】重连后重发离线操作
        function flushPendingOps() {
            const ops = [...pendingOps.value];
            pendingOps.value = [];
            for (const op of ops) {
                executeOperation(op);
            }
        }

        // 心跳响应
        function startHeartbeat() {
            clearInterval(heartbeatTimer);
            heartbeatTimer = setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ type: 'pong' }));
                }
            }, 15000);
        }

        // ── WebSocket 消息处理 ───────────────────────────────
        // 【修复问题1】所有消息处理都通过修改 ref.value 的属性触发响应式更新

        function handleWsMessage(msg) {
            switch (msg.type) {
                case 'connected':
                    connectionStatus.value = 'connected';
                    reconnectAttempts.value = 0;
                    onlineUsers.value = msg.online_users || [];
                    startHeartbeat();
                    // 重连后重发离线操作
                    if (pendingOps.value.length > 0) {
                        flushPendingOps();
                    }
                    break;

                case 'ping':
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({ type: 'pong' }));
                    }
                    break;

                case 'user_joined':
                case 'user_left':
                    // 【修复问题1】直接替换 ref 的 .value 触发视图更新
                    onlineUsers.value = msg.online_users || [];
                    break;

                case 'review_status_changed':
                    // 【修复问题1】关键修复:
                    // 错误做法: sections = newSections (reactive 直接赋值，视图不更新)
                    // 正确做法: 找到具体 section，逐字段修改属性，Vue Proxy 拦截 set 触发更新
                    updateSectionStatus(msg);
                    break;

                case 'annotation_created':
                    addRemoteAnnotation(msg);
                    break;

                case 'annotation_changed':
                    updateRemoteAnnotation(msg);
                    break;

                case 'conflict_detected':
                    // 【修复问题3】弹出冲突对话框
                    handleConflictNotification(msg);
                    break;

                case 'conflict_resolved':
                    updateRemoteAnnotation({
                        section_id: msg.section_id,
                        annotation: msg.annotation,
                    });
                    break;
            }
        }

        // 【修复问题1】正确的响应式更新 — 修改 ref 数组内对象的属性
        function updateSectionStatus(msg) {
            const idx = sections.value.findIndex(s => s.id === msg.section_id);
            if (idx === -1) return;
            // 直接修改数组元素的属性 — Vue 3 的 Proxy 能追踪到这些变化
            sections.value[idx].review_status = msg.status;
            sections.value[idx].reviewed_by = msg.reviewed_by;
            sections.value[idx].reviewed_at = msg.reviewed_at || null;
            // 触发数组变更通知（确保依赖此数组的计算属性/watcher 重新求值）
            sections.value = [...sections.value];
        }

        function addRemoteAnnotation(msg) {
            const idx = sections.value.findIndex(s => s.id === msg.section_id);
            if (idx === -1) return;
            const existing = sections.value[idx].annotations || [];
            if (!existing.find(a => a.id === msg.annotation.id)) {
                sections.value[idx].annotations = [...existing, msg.annotation];
                // 触发数组重新渲染
                sections.value = [...sections.value];
            }
        }

        function updateRemoteAnnotation(msg) {
            const ann = msg.annotation;
            if (!ann) return;
            const sIdx = sections.value.findIndex(s => s.id === msg.section_id);
            if (sIdx === -1) return;
            const aIdx = sections.value[sIdx].annotations.findIndex(a => a.id === ann.id);
            if (aIdx !== -1) {
                // 【修复问题1】逐字段更新 + 数组浅拷贝确保视图刷新
                Object.assign(sections.value[sIdx].annotations[aIdx], ann);
                sections.value = [...sections.value];
            }
        }

        // ── 操作发送（支持离线缓存）────────────────────────

        // 【修复问题2】统一操作入口 — 在线则直接发送，离线则缓存
        function sendOrQueue(operation) {
            if (connectionStatus.value === 'connected') {
                executeOperation(operation);
            } else {
                pendingOps.value.push(operation);
            }
        }

        async function executeOperation(op) {
            try {
                const res = await fetch(op.url, {
                    method: op.method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(op.body),
                });

                // 【修复问题3】检测 409 冲突响应
                if (res.status === 409) {
                    const data = await res.json();
                    conflict.value = {
                        annotationId: op.annotationId,
                        sectionId: op.sectionId,
                        myContent: data.your_content,
                        myVersion: data.your_version,
                        serverContent: data.server_content,
                        serverVersion: data.server_version,
                        serverAuthor: data.server_author,
                    };
                    conflictChoice.value = null;
                    return;
                }

                if (!res.ok) throw new Error(`HTTP ${res.status}`);

                const data = await res.json();
                if (op.onSuccess) op.onSuccess(data);
            } catch (err) {
                console.error('Operation failed:', err);
                // 如果是网络错误（离线状态下），放回队列
                if (!navigator.onLine || connectionStatus.value !== 'connected') {
                    pendingOps.value.push(op);
                }
            }
        }

        // ── 用户操作 ────────────────────────────────────────

        function setReviewStatus(section, status) {
            // 乐观更新本地状态
            const idx = sections.value.findIndex(s => s.id === section.id);
            if (idx !== -1) {
                sections.value[idx].review_status = status;
                sections.value[idx].reviewed_by = userId.value;
                sections.value = [...sections.value];
            }

            sendOrQueue({
                url: `/api/sections/${section.id}/review`,
                method: 'PUT',
                body: { status, reviewed_by: userId.value },
                onSuccess: (data) => {
                    // 用服务端返回的完整数据更新
                    if (idx !== -1) {
                        Object.assign(sections.value[idx], data);
                        sections.value = [...sections.value];
                    }
                },
            });
        }

        function addAnnotation(section) {
            const content = newAnnotationContent.value[section.id];
            if (!content || !content.trim()) return;

            sendOrQueue({
                url: `/api/sections/${section.id}/annotations`,
                method: 'POST',
                body: { author: userId.value, content: content.trim() },
                onSuccess: (data) => {
                    const idx = sections.value.findIndex(s => s.id === section.id);
                    if (idx !== -1) {
                        const existing = sections.value[idx].annotations || [];
                        if (!existing.find(a => a.id === data.id)) {
                            sections.value[idx].annotations = [...existing, data];
                            sections.value = [...sections.value];
                        }
                    }
                },
            });

            newAnnotationContent.value[section.id] = '';
        }

        function startEditAnnotation(ann) {
            editingAnnotation.value = ann.id;
            editContent.value = ann.content;
        }

        function saveAnnotation(ann) {
            // 【修复问题3】提交时携带当前持有的 version
            sendOrQueue({
                url: `/api/annotations/${ann.id}`,
                method: 'PUT',
                body: {
                    content: editContent.value,
                    author: userId.value,
                    version: ann.version,  // 乐观锁版本号
                },
                annotationId: ann.id,
                sectionId: ann.section_id,
                onSuccess: (data) => {
                    // 更新本地批注（包括新版本号）
                    for (const sec of sections.value) {
                        const aIdx = sec.annotations.findIndex(a => a.id === ann.id);
                        if (aIdx !== -1) {
                            Object.assign(sec.annotations[aIdx], data);
                            sections.value = [...sections.value];
                            break;
                        }
                    }
                    editingAnnotation.value = null;
                },
            });
        }

        // 【修复问题3】冲突解决
        function resolveConflict() {
            if (!conflict.value || !conflictChoice.value) return;

            const chosenContent = conflictChoice.value === 'mine'
                ? conflict.value.myContent
                : conflict.value.serverContent;

            executeOperation({
                url: `/api/annotations/${conflict.value.annotationId}/resolve-conflict`,
                method: 'PUT',
                body: {
                    content: chosenContent,
                    author: userId.value,
                    force: true,
                },
                onSuccess: (data) => {
                    // 更新本地数据
                    for (const sec of sections.value) {
                        const aIdx = sec.annotations.findIndex(a => a.id === data.id);
                        if (aIdx !== -1) {
                            Object.assign(sec.annotations[aIdx], data);
                            sections.value = [...sections.value];
                            break;
                        }
                    }
                    conflict.value = null;
                    conflictChoice.value = null;
                    editingAnnotation.value = null;
                },
            });
        }

        function handleConflictNotification(msg) {
            // 收到其他用户触发的冲突通知（从 WebSocket 广播来的）
            // 更新本地对应批注的版本信息
            for (const sec of sections.value) {
                const ann = sec.annotations.find(a => a.id === msg.annotation_id);
                if (ann) {
                    ann.version = msg.server_version;
                    ann.content = msg.server_content;
                    sections.value = [...sections.value];
                    break;
                }
            }
        }

        // ── 辅助函数 ────────────────────────────────────────

        function statusLabel(status) {
            return { pending: '待审核', approved: '已通过', flagged: '有问题' }[status] || status;
        }

        function formatTime(isoStr) {
            if (!isoStr) return '';
            try {
                const d = new Date(isoStr);
                return d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            } catch { return ''; }
        }

        // ── 初始化 ──────────────────────────────────────────

        async function loadReport() {
            try {
                let res = await fetch(`/api/reports/${reportId}`);
                if (res.status === 404) {
                    // 首次运行，创建种子数据
                    await fetch('/api/seed', { method: 'POST' });
                    res = await fetch(`/api/reports/${reportId}`);
                }
                const data = await res.json();
                report.value = { id: data.id, title: data.title };
                sections.value = data.sections || [];
            } catch (err) {
                console.error('Failed to load report:', err);
            }
        }

        onMounted(async () => {
            await loadReport();
            connectWebSocket();
        });

        onUnmounted(() => {
            if (ws) ws.close();
            clearTimeout(reconnectTimer);
            clearInterval(heartbeatTimer);
        });

        return {
            report, sections, userId, onlineUsers,
            connectionStatus, reconnectAttempts, pendingOps,
            editingAnnotation, editContent, newAnnotationContent,
            conflict, conflictChoice,
            statusLabel, formatTime,
            setReviewStatus, addAnnotation, startEditAnnotation,
            saveAnnotation, resolveConflict,
        };
    },
});

app.mount('#app');
