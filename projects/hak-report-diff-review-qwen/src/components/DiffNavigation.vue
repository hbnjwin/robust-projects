<template>
  <div class="diff-navigation">
    <div class="diff-nav-info">
      <span class="diff-nav-label">差异导航</span>
      <span class="diff-nav-counter">{{ currentDiffLabel }}</span>
      <el-tag v-if="pendingCount > 0" type="warning" size="small">
        {{ pendingCount }} 项待处理
      </el-tag>
      <el-tag v-else type="success" size="small">全部已处理</el-tag>
    </div>
    <div class="diff-nav-buttons">
      <el-button size="small" :icon="ArrowUp" @click="$emit('prev')" :disabled="totalDiffs === 0">
        上一个差异
      </el-button>
      <el-button size="small" :icon="ArrowDown" @click="$emit('next')" :disabled="totalDiffs === 0">
        下一个差异
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'

defineProps<{
  currentDiffLabel: string
  totalDiffs: number
  pendingCount: number
}>()

defineEmits<{
  prev: []
  next: []
}>()
</script>

<style scoped>
.diff-navigation {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  border-radius: 8px 8px 0 0;
}

.diff-nav-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.diff-nav-label {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.diff-nav-counter {
  font-family: 'Courier New', monospace;
  font-size: 14px;
  color: #606266;
  background: #fff;
  padding: 2px 10px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
}

.diff-nav-buttons {
  display: flex;
  gap: 8px;
}
</style>
