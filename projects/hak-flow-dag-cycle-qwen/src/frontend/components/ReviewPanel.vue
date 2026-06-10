<!--
  ReviewPanel.vue - 多人协作审核面板

  集成 useReviewWebSocket composable，修复三个 WebSocket 同步问题：

  问题1 修复（视图不更新）：
    - sections 使用 shallowRef + triggerRef，WebSocket 消息通过 applyUpdate()
      创建新数组引用来驱动 Vue 视图刷新
    - 审核员 A 标记状态后，审核员 B 的页面自动刷新，无需手动 F5

  问题2 修复（断线无提示）：
    - 顶部连接状态指示器（绿色/黄色/红色圆点 + 文字提示）
    - 断线时显示黄色横幅："连接已断开，正在重连..."
    - 离线操作时显示待同步计数："有 N 个操作待同步"
    - 重连后自动重放缓存的操作

  问题3 修复（冲突覆盖）：
    - 冲突检测对话框：显示"你的版本"和"服务端版本"的 diff 对比
    - 三个选项：保留我的 / 采用服务端 / 手动合并
    - 解决后广播通知其他审核员
-->
<template>
  <div class="review-panel">
    <!-- ═══ 问题2 修复：连接状态指示器 ═══ -->
    <header class="panel-header">
      <h2>{{ title }}</h2>
      <div class="header-info">
        <!-- 连接状态指示灯 -->
        <span class="connection-indicator" :class="connectionStatus">
          <span class="status-dot" />
          {{ statusText }}
        </span>
        <!-- 在线审核员列表 -->
        <span class="online-users">
          在线: {{ onlineUsers.length }} 人
          <span
            v-for="user in onlineUsers"
            :key="user"
            class="user-badge"
          >
            {{ user }}
          </span>
        </span>
      </div>
    </header>

    <!-- 问题2 修复：断线警告横幅 -->
    <div
      v-if="connectionStatus !== 'connected'"
      class="connection-warning"
      :class="connectionStatus"
    >
      <span v-if="connectionStatus === 'reconnecting'">
        ⚠️ 连接已断开，正在重新连接...
      </span>
      <span v-else-if="connectionStatus === 'connecting'">
        ⏳ 正在连接服务器...
      </span>
      <span v-else>
        ❌ 连接已断开。您的操作将在恢复连接后自动同步。
      </span>
    </div>

    <!-- 问题2 修复：离线操作待同步提示 -->
    <div v-if="pendingCount > 0" class="pending-ops-bar">
      📋 有 {{ pendingCount }} 个操作待同步（网络恢复后自动提交）
    </div>

    <!-- 错误提示 -->
    <div v-if="lastError" class="error-banner">
      ⚠️ {{ lastError }}
    </div>

    <!-- ═══ 段落审核列表 ═══ -->
    <div class="sections-list">
      <div
        v-for="section in sections"
        :key="section.id"
        class="section-card"
        :class="'status-' + section.review_status"
      >
        <div class="section-header">
          <span class="section-order">段落 {{ section.order + 1 }}</span>
          <span
            class="status-badge"
            :class="'badge-' + section.review_status"
          >
            {{ statusLabel(section.review_status) }}
          </span>
          <span v-if="section.reviewed_by" class="reviewer">
            由 {{ section.reviewed_by }} 审核
          </span>
        </div>

        <p class="section-content">{{ section.content }}</p>

        <!-- 审核操作按钮 -->
        <div class="review-actions">
          <button
            :disabled="connectionStatus === 'disconnected' && pendingCount === 0"
            :class="{ active: section.review_status === 'approved' }"
            @click="markSectionStatus(section.id, 'approved')"
          >
            ✓ 通过
          </button>
          <button
            :disabled="connectionStatus === 'disconnected' && pendingCount === 0"
            :class="{ active: section.review_status === 'flagged' }"
            @click="markSectionStatus(section.id, 'flagged')"
          >
            ⚠ 有问题
          </button>
          <button
            @click="markSectionStatus(section.id, 'pending')"
          >
            ↩ 重置
          </button>
        </div>

        <!-- 批注区域 -->
        <div class="annotations-area">
          <h4>
            批注 ({{ section.annotations.length }})
          </h4>

          <div
            v-for="ann in section.annotations"
            :key="ann.id"
            class="annotation-item"
          >
            <div class="annotation-meta">
              <strong>{{ ann.author }}</strong>
              <span class="annotation-version">v{{ ann.version }}</span>
              <span class="annotation-time">{{ formatTime(ann.updated_at) }}</span>
            </div>
            <p class="annotation-content">{{ ann.content }}</p>
          </div>

          <!-- 新建批注 -->
          <div class="new-annotation">
            <textarea
              v-model="newAnnotationText[section.id]"
              placeholder="添加批注..."
              rows="2"
            />
            <button
              :disabled="!newAnnotationText[section.id]?.trim()"
              @click="handleCreateAnnotation(section.id)"
            >
              提交批注
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ 问题3 修复：冲突解决对话框 ═══ -->
    <Teleport to="body">
      <div v-if="activeConflict" class="conflict-overlay" @click.self="/* 不关闭 */">
        <div class="conflict-dialog">
          <h3>⚠️ 编辑冲突</h3>
          <p class="conflict-explanation">
            审核员 <strong>{{ activeConflict.server_author }}</strong>
            已修改了这条批注（版本 v{{ activeConflict.server_version }}），
            而您的版本是 v{{ activeConflict.your_version }}。
            请选择如何解决冲突：
          </p>

          <div class="conflict-comparison">
            <div class="conflict-version">
              <h4>📝 您的版本 (v{{ activeConflict.your_version }})</h4>
              <div class="version-content">
                {{ activeConflict.your_content }}
              </div>
            </div>
            <div class="conflict-version">
              <h4>🖥️ 服务端版本 (v{{ activeConflict.server_version }})</h4>
              <div class="version-content">
                {{ activeConflict.server_content }}
              </div>
            </div>
          </div>

          <!-- 手动合并编辑区 -->
          <div class="conflict-merge">
            <h4>✏️ 手动合并结果</h4>
            <textarea
              v-model="mergedContent"
              rows="4"
              placeholder="在此编辑合并后的内容..."
            />
          </div>

          <div class="conflict-actions">
            <button class="btn-keep-mine" @click="resolveWithMyContent">
              保留我的版本
            </button>
            <button class="btn-keep-server" @click="resolveWithServerContent">
              采用服务端版本
            </button>
            <button
              class="btn-merge"
              :disabled="!mergedContent?.trim()"
              @click="resolveWithMergedContent"
            >
              使用合并结果
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useReviewWebSocket } from '../composables/useReviewWebSocket';

// ── Props ─────────────────────────────────────────────────

const props = defineProps<{
  reportId: number;
  userId: string;
  title?: string;
}>();

// ── WebSocket composable ──────────────────────────────────

const {
  sections,
  connectionStatus,
  onlineUsers,
  activeConflict,
  pendingCount,
  lastError,
  connect,
  setSections,
  markSectionStatus,
  createAnnotation,
  resolveConflict,
} = useReviewWebSocket(props.reportId, props.userId);

// ── 本地状态 ──────────────────────────────────────────────

const newAnnotationText = ref<Record<number, string>>({});
const mergedContent = ref('');

// ── 计算属性 ──────────────────────────────────────────────

const statusText = computed(() => {
  const map: Record<string, string> = {
    connected: '已连接',
    connecting: '连接中...',
    reconnecting: '正在重连...',
    disconnected: '已断开',
  };
  return map[connectionStatus.value] || connectionStatus.value;
});

// ── 冲突解决时，自动填充合并编辑区 ──

watch(
  activeConflict,
  (conflict) => {
    if (conflict) {
      // 默认将两个版本拼接作为合并起点
      mergedContent.value =
        `${conflict.your_content}\n\n--- ${conflict.server_author} 的版本 ---\n${conflict.server_content}`;
    } else {
      mergedContent.value = '';
    }
  },
);

// ── 初始化 ────────────────────────────────────────────────

onMounted(async () => {
  // 从 REST API 加载报告数据
  try {
    const resp = await fetch(`/api/reports/${props.reportId}`);
    if (resp.ok) {
      const data = await resp.json();
      setSections(data.sections || []);
    }
  } catch {
    // 加载失败时 sections 保持空数组
  }

  // 建立 WebSocket 连接
  connect();
});

// ── 方法 ──────────────────────────────────────────────────

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    flagged: '有问题',
  };
  return map[status] || status;
}

function formatTime(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('zh-CN');
  } catch {
    return iso;
  }
}

async function handleCreateAnnotation(sectionId: number): Promise<void> {
  const text = newAnnotationText.value[sectionId]?.trim();
  if (!text) return;

  const result = await createAnnotation(sectionId, text, props.userId);
  if (result) {
    newAnnotationText.value[sectionId] = '';
  }
}

/** 问题3：冲突解决 - 保留我的版本 */
async function resolveWithMyContent(): Promise<void> {
  if (!activeConflict.value) return;
  await resolveConflict(
    activeConflict.value.annotation_id,
    activeConflict.value.your_content,
    props.userId,
  );
}

/** 问题3：冲突解决 - 采用服务端版本 */
async function resolveWithServerContent(): Promise<void> {
  if (!activeConflict.value) return;
  await resolveConflict(
    activeConflict.value.annotation_id,
    activeConflict.value.server_content,
    props.userId,
  );
}

/** 问题3：冲突解决 - 使用手动合并结果 */
async function resolveWithMergedContent(): Promise<void> {
  if (!activeConflict.value || !mergedContent.value.trim()) return;
  await resolveConflict(
    activeConflict.value.annotation_id,
    mergedContent.value,
    props.userId,
  );
}
</script>

<style scoped>
.review-panel {
  max-width: 960px;
  margin: 0 auto;
  padding: 16px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

/* ── 头部 ── */
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 2px solid #e2e8f0;
  margin-bottom: 16px;
}

.header-info {
  display: flex;
  gap: 16px;
  align-items: center;
  font-size: 14px;
}

/* ── 问题2 修复：连接状态指示灯 ── */
.connection-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}

.connection-indicator.connected .status-dot {
  background: #22c55e;
  box-shadow: 0 0 6px #22c55e;
}

.connection-indicator.connecting .status-dot,
.connection-indicator.reconnecting .status-dot {
  background: #f59e0b;
  animation: pulse 1s infinite;
}

.connection-indicator.disconnected .status-dot {
  background: #ef4444;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ── 在线用户 ── */
.online-users {
  color: #64748b;
}

.user-badge {
  display: inline-block;
  background: #e2e8f0;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  margin-left: 4px;
}

/* ── 问题2 修复：连接警告横幅 ── */
.connection-warning {
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 500;
}

.connection-warning.reconnecting {
  background: #fef3c7;
  color: #92400e;
  border: 1px solid #fcd34d;
}

.connection-warning.connecting {
  background: #dbeafe;
  color: #1e40af;
  border: 1px solid #93c5fd;
}

.connection-warning.disconnected {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}

/* ── 问题2 修复：离线操作提示 ── */
.pending-ops-bar {
  padding: 8px 16px;
  background: #fff7ed;
  color: #9a3412;
  border: 1px solid #fdba74;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}

/* ── 错误横幅 ── */
.error-banner {
  padding: 8px 16px;
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}

/* ── 段落卡片 ── */
.sections-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  transition: border-color 0.3s;
}

.section-card.status-approved {
  border-color: #86efac;
  background: #f0fdf4;
}

.section-card.status-flagged {
  border-color: #fca5a5;
  background: #fef2f2;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.section-order {
  font-weight: 600;
  color: #334155;
}

.status-badge {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge-pending { background: #f1f5f9; color: #475569; }
.badge-approved { background: #dcfce7; color: #166534; }
.badge-flagged { background: #fee2e2; color: #991b1b; }

.reviewer {
  font-size: 12px;
  color: #94a3b8;
}

.section-content {
  line-height: 1.6;
  color: #334155;
  margin: 8px 0 12px;
}

/* ── 审核按钮 ── */
.review-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.review-actions button {
  padding: 6px 14px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.review-actions button:hover:not(:disabled) {
  background: #f8fafc;
}

.review-actions button.active {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #1d4ed8;
}

.review-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── 批注区域 ── */
.annotations-area {
  border-top: 1px solid #e2e8f0;
  padding-top: 12px;
}

.annotations-area h4 {
  font-size: 14px;
  color: #475569;
  margin-bottom: 8px;
}

.annotation-item {
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 8px;
}

.annotation-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.annotation-version {
  color: #94a3b8;
  font-family: monospace;
}

.annotation-time {
  color: #94a3b8;
}

.annotation-content {
  font-size: 14px;
  color: #334155;
  line-height: 1.5;
}

.new-annotation {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.new-annotation textarea {
  flex: 1;
  padding: 8px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
  resize: vertical;
}

.new-annotation button {
  padding: 8px 16px;
  background: #3b82f6;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}

.new-annotation button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ── 问题3 修复：冲突解决对话框 ── */
.conflict-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.conflict-dialog {
  background: white;
  border-radius: 16px;
  padding: 24px;
  max-width: 700px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.25);
}

.conflict-dialog h3 {
  margin-bottom: 8px;
  color: #991b1b;
}

.conflict-explanation {
  color: #64748b;
  font-size: 14px;
  margin-bottom: 16px;
}

.conflict-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.conflict-version h4 {
  font-size: 13px;
  color: #475569;
  margin-bottom: 6px;
}

.version-content {
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  min-height: 60px;
}

.conflict-merge {
  margin-bottom: 16px;
}

.conflict-merge h4 {
  font-size: 13px;
  color: #475569;
  margin-bottom: 6px;
}

.conflict-merge textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.5;
  resize: vertical;
  box-sizing: border-box;
}

.conflict-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.conflict-actions button {
  padding: 8px 18px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}

.btn-keep-mine {
  background: #3b82f6;
  color: white;
}

.btn-keep-server {
  background: #8b5cf6;
  color: white;
}

.btn-merge {
  background: #059669;
  color: white;
}

.btn-merge:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
