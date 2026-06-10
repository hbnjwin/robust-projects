<template>
  <div class="diff-viewer">
    <!-- 顶部导航栏 -->
    <DiffNavigation
      :current-diff-label="currentDiffLabel"
      :total-diffs="totalDiffs"
      :pending-count="pendingDiffs"
      @next="goToNextDiff"
      @prev="goToPrevDiff"
    />

    <!-- 标题栏 -->
    <div class="diff-header">
      <div class="diff-header-side">
        <el-tag type="info">{{ oldTitle || '原始版本' }}</el-tag>
      </div>
      <div class="diff-header-side">
        <el-tag type="primary">{{ newTitle || '修改版本' }}</el-tag>
      </div>
    </div>

    <!-- Diff内容区 -->
    <div class="diff-content">
      <div
        v-for="block in blocks"
        :key="block.id"
        :id="block.id"
        class="diff-block"
        :class="getBlockClass(block)"
      >
        <!-- 表格类型：使用DiffTable组件保持表格结构 (Bug Fix #2) -->
        <template v-if="block.type === 'table' && block.tableDiff">
          <div class="diff-block-table">
            <DiffTable
              :table-diff="block.tableDiff"
              :block-id="block.id"
              @accept-cell="(r, c) => acceptTableCell(block.id, r, c)"
              @reject-cell="(r, c) => rejectTableCell(block.id, r, c)"
            />
          </div>
        </template>

        <!-- 文本/标题/列表类型：左右并排显示 -->
        <template v-else>
          <div class="diff-block-text">
            <!-- 左侧：旧版本 -->
            <div class="diff-side diff-side-old">
              <div class="diff-text-content">
                <!-- Bug Fix #1: 字符级diff渲染 -->
                <template v-for="(seg, idx) in block.segments" :key="'old-' + idx">
                  <span v-if="seg.type === 'equal'" class="diff-equal">{{ seg.value }}</span>
                  <del v-else-if="seg.type === 'removed'" class="diff-removed">{{ seg.value }}</del>
                  <span v-else-if="seg.type === 'modified'" class="diff-modified-old">{{ seg.value }}</span>
                  <!-- added 类型在左侧不显示 -->
                </template>
                <span v-if="block.segments.length === 0 && block.oldValue" class="diff-equal">{{ block.oldValue }}</span>
              </div>
            </div>
            <!-- 右侧：新版本 -->
            <div class="diff-side diff-side-new">
              <div class="diff-text-content">
                <!-- Bug Fix #1: 字符级diff渲染 -->
                <template v-for="(seg, idx) in block.segments" :key="'new-' + idx">
                  <span v-if="seg.type === 'equal'" class="diff-equal">{{ seg.value }}</span>
                  <ins v-else-if="seg.type === 'added'" class="diff-added">{{ seg.value }}</ins>
                  <ins v-else-if="seg.type === 'modified'" class="diff-added">{{ seg.value }}</ins>
                  <!-- removed 类型在右侧不显示 -->
                </template>
                <span v-if="block.segments.length === 0 && block.newValue" class="diff-equal">{{ block.newValue }}</span>
              </div>
            </div>
          </div>

          <!-- Bug Fix #4: 接受/拒绝操作按钮 -->
          <div v-if="block.hasChanges && block.status === 'pending'" class="diff-block-actions">
            <el-button
              type="success"
              size="small"
              :icon="Check"
              @click="acceptChange(block.id)"
            >
              接受修改
            </el-button>
            <el-button
              type="danger"
              size="small"
              :icon="Close"
              @click="rejectChange(block.id)"
            >
              拒绝修改
            </el-button>
          </div>

          <!-- Bug Fix #4: 已处理状态标记 -->
          <div v-if="block.status === 'accepted'" class="diff-block-status status-accepted">
            <el-icon><Check /></el-icon> 已接受
          </div>
          <div v-if="block.status === 'rejected'" class="diff-block-status status-rejected">
            <el-icon><Close /></el-icon> 已拒绝
          </div>
        </template>
      </div>

      <!-- 空状态 -->
      <el-empty v-if="blocks.length === 0" description="两份报告内容一致，无差异" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Check, Close } from '@element-plus/icons-vue'
import DiffNavigation from './DiffNavigation.vue'
import DiffTable from './DiffTable.vue'
import { useDiffViewer } from '@/composables/useDiffViewer'
import type { DiffBlock } from '@/types/diff'

const props = withDefaults(defineProps<{
  oldContent: string
  newContent: string
  oldTitle?: string
  newTitle?: string
  headerHeight?: number
}>(), {
  oldTitle: '原始版本',
  newTitle: '修改版本',
  headerHeight: 64,
})

const {
  blocks,
  totalDiffs,
  pendingDiffs,
  currentDiffLabel,
  goToNextDiff,
  goToPrevDiff,
  acceptChange,
  rejectChange,
  acceptTableCell,
  rejectTableCell,
} = useDiffViewer(props.oldContent, props.newContent, props.headerHeight)

/**
 * Bug Fix #4: 根据block状态返回CSS class
 * pending状态有黄色边框高亮；accepted/rejected后高亮消失
 */
function getBlockClass(block: DiffBlock) {
  if (!block.hasChanges) return 'diff-block-unchanged'
  return {
    'diff-block-changed': true,
    'diff-block-pending': block.status === 'pending',
    'diff-block-accepted': block.status === 'accepted',
    'diff-block-rejected': block.status === 'rejected',
  }
}
</script>

<style scoped>
.diff-viewer {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

/* 标题栏 */
.diff-header {
  display: flex;
  border-bottom: 2px solid #e4e7ed;
  background: #fafafa;
}

.diff-header-side {
  flex: 1;
  padding: 10px 20px;
  text-align: center;
}

.diff-header-side:first-child {
  border-right: 1px solid #e4e7ed;
}

/* 内容区 */
.diff-content {
  padding: 16px;
}

/* Diff块 */
.diff-block {
  margin-bottom: 12px;
  border-radius: 6px;
  transition: border-color 0.3s, background-color 0.3s;
}

/* Bug Fix #4: 待处理差异 - 黄色高亮边框 */
.diff-block-pending {
  border: 1px solid #e6a23c;
  background-color: #fdf6ec;
}

/* Bug Fix #4: 已接受 - 高亮消失，变为淡绿背景 */
.diff-block-accepted {
  border: 1px solid #e4e7ed;
  background-color: #f0f9eb;
}

/* Bug Fix #4: 已拒绝 - 高亮消失，变为淡红背景 */
.diff-block-rejected {
  border: 1px solid #e4e7ed;
  background-color: #fef0f0;
}

.diff-block-unchanged {
  border: 1px solid transparent;
}

/* 文本块并排布局 */
.diff-block-text {
  display: flex;
}

.diff-side {
  flex: 1;
  padding: 12px 16px;
  min-height: 40px;
}

.diff-side-old {
  border-right: 1px solid #e4e7ed;
  background-color: rgba(0, 0, 0, 0.02);
}

.diff-side-new {
  background-color: rgba(0, 0, 0, 0.01);
}

.diff-text-content {
  line-height: 1.8;
  font-size: 14px;
  word-break: break-all;
}

/* Bug Fix #1: 字符级diff样式 - 精确到单个汉字 */
.diff-equal {
  color: #303133;
}

.diff-removed {
  background-color: #fde2e2;
  color: #f56c6c;
  text-decoration: line-through;
  padding: 1px 3px;
  border-radius: 3px;
  font-style: normal;
}

.diff-added {
  background-color: #e1f3d8;
  color: #67c23a;
  text-decoration: none;
  padding: 1px 3px;
  border-radius: 3px;
  font-style: normal;
}

.diff-modified-old {
  background-color: #fde2e2;
  color: #f56c6c;
  text-decoration: line-through;
  padding: 1px 3px;
  border-radius: 3px;
}

/* 表格diff区域 */
.diff-block-table {
  padding: 8px;
}

/* 操作按钮区 */
.diff-block-actions {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  border-top: 1px dashed #e4e7ed;
  justify-content: flex-end;
}

/* 已处理状态标签 */
.diff-block-status {
  padding: 4px 16px;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
}

.status-accepted {
  color: #67c23a;
}

.status-rejected {
  color: #f56c6c;
}
</style>
