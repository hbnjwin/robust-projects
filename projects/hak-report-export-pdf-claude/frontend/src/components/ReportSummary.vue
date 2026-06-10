<template>
  <div class="report-summary">
    <div class="report-summary__header">
      <h1>{{ report.title }}</h1>
      <span :class="['status-badge', `status-badge--${report.status}`]">
        {{ statusLabel(report.status) }}
      </span>
    </div>
    <div class="report-summary__meta">
      <span>作者：{{ report.author }}</span>
      <span v-if="report.reviewer">审核人：{{ report.reviewer }}</span>
      <span>创建：{{ formatDate(report.createdAt) }}</span>
      <span>更新：{{ formatDate(report.updatedAt) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Report } from '@/types/report'

defineProps<{
  report: Report
}>()

function statusLabel(status: Report['status']): string {
  const map: Record<Report['status'], string> = {
    draft: '草稿',
    pending: '待审核',
    approved: '已通过',
    rejected: '已拒绝'
  }
  return map[status]
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.report-summary {
  padding: 20px 24px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin-bottom: 20px;
}

.report-summary__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.report-summary__header h1 {
  font-size: 20px;
  margin: 0;
  color: #111827;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  white-space: nowrap;
}

.status-badge--draft { background: #f3f4f6; color: #6b7280; }
.status-badge--pending { background: #fef3c7; color: #92400e; }
.status-badge--approved { background: #d1fae5; color: #065f46; }
.status-badge--rejected { background: #fee2e2; color: #991b1b; }

.report-summary__meta {
  display: flex;
  gap: 20px;
  font-size: 13px;
  color: #6b7280;
}
</style>
