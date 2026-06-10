<template>
  <div class="diff-table-wrapper">
    <table class="diff-table" v-bind="tableAttrsObj">
      <tbody>
        <tr v-for="(row, rowIdx) in tableDiff.rows" :key="rowIdx" class="diff-table-row">
          <td
            v-for="(cell, colIdx) in row.cells"
            :key="colIdx"
            class="diff-table-cell"
            :class="getCellClass(cell)"
          >
            <div class="cell-content">
              <!-- Bug Fix #1: 字符级diff渲染，中文逐字标注 -->
              <template v-for="(seg, segIdx) in cell.segments" :key="segIdx">
                <span
                  v-if="seg.type === 'equal'"
                  class="diff-equal"
                >{{ seg.value }}</span>
                <del
                  v-else-if="seg.type === 'removed'"
                  class="diff-removed"
                >{{ seg.value }}</del>
                <ins
                  v-else-if="seg.type === 'added'"
                  class="diff-added"
                >{{ seg.value }}</ins>
                <span
                  v-else-if="seg.type === 'modified'"
                  class="diff-modified-old"
                >{{ seg.value }}</span>
              </template>
            </div>
            <!-- Bug Fix #4: 接受/拒绝按钮，处理后高亮消失 -->
            <div v-if="isCellPending(cell)" class="cell-actions">
              <el-button
                type="success"
                size="small"
                circle
                :icon="Check"
                @click="$emit('acceptCell', rowIdx, colIdx)"
                title="接受修改"
              />
              <el-button
                type="danger"
                size="small"
                circle
                :icon="Close"
                @click="$emit('rejectCell', rowIdx, colIdx)"
                title="拒绝修改"
              />
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check, Close } from '@element-plus/icons-vue'
import type { TableDiff, TableCellDiff } from '@/types/diff'

const props = defineProps<{
  tableDiff: TableDiff
  blockId: string
}>()

defineEmits<{
  acceptCell: [rowIdx: number, colIdx: number]
  rejectCell: [rowIdx: number, colIdx: number]
}>()

const tableAttrsObj = computed(() => {
  if (!props.tableDiff.tableAttrs) return {}
  const attrs: Record<string, string> = {}
  const regex = /(\w[\w-]*)=(?:"([^"]*)"|'([^']*)')/g
  let match: RegExpExecArray | null
  while ((match = regex.exec(props.tableDiff.tableAttrs)) !== null) {
    attrs[match[1]] = match[2] || match[3] || ''
  }
  return attrs
})

function getCellClass(cell: TableCellDiff) {
  const hasChanges = cell.segments.some(s => s.type !== 'equal')
  if (!hasChanges) return ''

  return {
    'cell-pending': cell.status === 'pending',
    'cell-accepted': cell.status === 'accepted',
    'cell-rejected': cell.status === 'rejected',
  }
}

function isCellPending(cell: TableCellDiff): boolean {
  const hasChanges = cell.segments.some(s => s.type !== 'equal')
  return hasChanges && cell.status === 'pending'
}
</script>

<style scoped>
.diff-table-wrapper {
  overflow-x: auto;
  margin: 8px 0;
}

.diff-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.diff-table-row {
  border-bottom: 1px solid #ebeef5;
}

.diff-table-cell {
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  vertical-align: top;
  position: relative;
  min-width: 80px;
}

.cell-content {
  line-height: 1.6;
}

/* Bug Fix #1: 字符级diff高亮样式 - 精确到单个汉字 */
.diff-equal {
  color: #303133;
}

.diff-removed {
  background-color: #fef0f0;
  color: #f56c6c;
  text-decoration: line-through;
  padding: 1px 2px;
  border-radius: 2px;
}

.diff-added {
  background-color: #f0f9eb;
  color: #67c23a;
  text-decoration: none;
  padding: 1px 2px;
  border-radius: 2px;
}

.diff-modified-old {
  background-color: #fef0f0;
  color: #f56c6c;
  text-decoration: line-through;
  padding: 1px 2px;
  border-radius: 2px;
}

/* Bug Fix #4: 待处理单元格有边框高亮 */
.cell-pending {
  border: 2px solid #e6a23c;
  background-color: #fdf6ec;
}

/* Bug Fix #4: 已接受/拒绝后移除高亮，恢复正常样式 */
.cell-accepted {
  background-color: #f0f9eb;
  border-color: #e4e7ed;
}

.cell-rejected {
  background-color: #fef0f0;
  border-color: #e4e7ed;
}

.cell-actions {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px dashed #dcdfe6;
}
</style>
