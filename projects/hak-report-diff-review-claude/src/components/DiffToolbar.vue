<script setup lang="ts">
defineProps<{
  currentIndex: number
  totalChanges: number
  pendingCount: number
  processedCount: number
  allProcessed: boolean
}>()

defineEmits<{
  prev: []
  next: []
  acceptAll: []
  rejectAll: []
}>()
</script>

<template>
  <div class="diff-toolbar">
    <div class="toolbar-left">
      <h3 class="toolbar-title">报告Diff对比审核</h3>
      <span class="toolbar-stats">
        共 <strong>{{ totalChanges }}</strong> 处差异，
        已处理 <strong>{{ processedCount }}</strong> 处，
        剩余 <strong>{{ pendingCount }}</strong> 处
      </span>
    </div>
    <div class="toolbar-center">
      <el-button-group>
        <el-button
          :icon="ArrowUp"
          @click="$emit('prev')"
          :disabled="totalChanges === 0"
          title="上一个差异"
        />
        <el-button disabled style="min-width: 80px; cursor: default">
          {{ totalChanges > 0 ? `${currentIndex + 1} / ${totalChanges}` : '无差异' }}
        </el-button>
        <el-button
          :icon="ArrowDown"
          @click="$emit('next')"
          :disabled="totalChanges === 0"
          title="下一个差异"
        />
      </el-button-group>
    </div>
    <div class="toolbar-right">
      <el-button type="success" plain @click="$emit('acceptAll')" :disabled="allProcessed">
        全部接受
      </el-button>
      <el-button type="danger" plain @click="$emit('rejectAll')" :disabled="allProcessed">
        全部拒绝
      </el-button>
    </div>
  </div>
</template>

<script lang="ts">
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'
export default { components: { ArrowUp, ArrowDown } }
</script>

<style scoped>
.diff-toolbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  z-index: 100;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.toolbar-title {
  margin: 0;
  font-size: 16px;
  white-space: nowrap;
}

.toolbar-stats {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.toolbar-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.toolbar-right {
  display: flex;
  gap: 8px;
}
</style>
