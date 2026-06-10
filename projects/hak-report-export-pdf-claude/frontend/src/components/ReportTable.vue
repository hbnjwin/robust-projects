<template>
  <div class="report-table">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>标题</th>
          <th>状态</th>
          <th>作者</th>
          <th>更新时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="report in reports" :key="report.id">
          <td>{{ report.id }}</td>
          <td>{{ report.title }}</td>
          <td>
            <span :class="['status-badge', `status-badge--${report.status}`]">
              {{ statusLabel(report.status) }}
            </span>
          </td>
          <td>{{ report.author }}</td>
          <td>{{ formatDate(report.updatedAt) }}</td>
          <td>
            <button class="btn-link" @click="$emit('view', report.id)">查看</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-if="reports.length === 0" class="report-table__empty">
      暂无数据
    </div>
    <div class="report-table__pagination">
      <button
        :disabled="currentPage <= 1"
        @click="$emit('page-change', String(currentPage - 1))"
      >
        上一页
      </button>
      <span>第 {{ currentPage }} 页 / 共 {{ totalPages }} 页（{{ total }} 条）</span>
      <button
        :disabled="currentPage >= totalPages"
        @click="$emit('page-change', String(currentPage + 1))"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Report } from '@/types/report'

const props = defineProps<{
  reports: Report[]
  total: number
  currentPage: number
  pageSize: number
}>()

defineEmits<{
  view: [id: string]
  'page-change': [page: string]
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

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
.report-table table {
  width: 100%;
  border-collapse: collapse;
}

.report-table th,
.report-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
}

.report-table th {
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.status-badge--draft { background: #f3f4f6; color: #6b7280; }
.status-badge--pending { background: #fef3c7; color: #92400e; }
.status-badge--approved { background: #d1fae5; color: #065f46; }
.status-badge--rejected { background: #fee2e2; color: #991b1b; }

.report-table__empty {
  text-align: center;
  padding: 48px;
  color: #9ca3af;
}

.report-table__pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 16px;
}

.report-table__pagination button {
  padding: 6px 16px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: white;
  cursor: pointer;
  font-size: 14px;
}

.report-table__pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.report-table__pagination span {
  font-size: 14px;
  color: #6b7280;
}

.btn-link {
  background: none;
  border: none;
  color: #3b82f6;
  cursor: pointer;
  font-size: 14px;
}

.btn-link:hover {
  text-decoration: underline;
}
</style>
