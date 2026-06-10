<script setup lang="ts">
defineProps<{
  report: {
    id: number
    title: string
    status: 'pending' | 'approved' | 'rejected'
    reviewer: string
    createdAt: string
  }
}>()

const statusMap: Record<string, { label: string; class: string }> = {
  pending: { label: '待审核', class: 'status-pending' },
  approved: { label: '已审核', class: 'status-approved' },
  rejected: { label: '已驳回', class: 'status-rejected' },
}
</script>

<template>
  <div class="report-item">
    <div class="report-title">{{ report.title }}</div>
    <div class="report-meta">
      <span :class="['status-tag', statusMap[report.status].class]">
        {{ statusMap[report.status].label }}
      </span>
      <span class="reviewer">审核人: {{ report.reviewer }}</span>
      <span class="date">{{ report.createdAt }}</span>
    </div>
  </div>
</template>

<style scoped>
.report-item {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
  background: #fff;
}

.report-title {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  word-break: break-all;
}

.report-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.status-tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-pending {
  background: #fdf6ec;
  color: #e6a23c;
}

.status-approved {
  background: #f0f9eb;
  color: #67c23a;
}

.status-rejected {
  background: #fef0f0;
  color: #f56c6c;
}

.reviewer,
.date {
  color: #909399;
}
</style>
