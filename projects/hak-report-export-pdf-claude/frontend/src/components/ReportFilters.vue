<template>
  <div class="report-filters">
    <div class="report-filters__field">
      <label>状态</label>
      <select :value="filters.status" @change="onStatusChange">
        <option value="">全部</option>
        <option value="draft">草稿</option>
        <option value="pending">待审核</option>
        <option value="approved">已通过</option>
        <option value="rejected">已拒绝</option>
      </select>
    </div>
    <div class="report-filters__field">
      <label>关键词</label>
      <input
        type="text"
        :value="filters.keyword"
        placeholder="搜索报告标题..."
        @keyup.enter="onKeywordSubmit"
        @change="onKeywordSubmit"
      />
    </div>
    <button class="report-filters__reset" @click="$emit('reset')">
      重置
    </button>
  </div>
</template>

<script setup lang="ts">
import type { ReportListFilters } from '@/types/report'

defineProps<{
  filters: ReportListFilters
}>()

const emit = defineEmits<{
  update: [patch: Partial<ReportListFilters>]
  reset: []
}>()

function onStatusChange(e: Event) {
  const value = (e.target as HTMLSelectElement).value
  emit('update', { status: value, page: '1' })
}

function onKeywordSubmit(e: Event) {
  const value = (e.target as HTMLInputElement).value
  emit('update', { keyword: value, page: '1' })
}
</script>

<style scoped>
.report-filters {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  padding: 16px;
  background: #f9fafb;
  border-radius: 8px;
  margin-bottom: 16px;
}

.report-filters__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.report-filters__field label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.report-filters__field select,
.report-filters__field input {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  min-width: 160px;
}

.report-filters__reset {
  padding: 8px 16px;
  background: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #374151;
}

.report-filters__reset:hover {
  background: #e5e7eb;
}
</style>
