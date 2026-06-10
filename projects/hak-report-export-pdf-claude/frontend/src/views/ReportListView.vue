<template>
  <div class="report-list-view">
    <h1>报告列表</h1>

    <p v-if="errorMessage" class="error-toast">{{ errorMessage }}</p>

    <ReportFilters
      :filters="filters"
      @update="updateFilters"
      @reset="resetFilters"
    />

    <div v-if="listStore.loading" class="loading-hint">加载中...</div>
    <div v-else-if="listStore.error" class="error-hint">
      {{ listStore.error }}
      <button @click="fetchData">重试</button>
    </div>
    <ReportTable
      v-else
      :reports="listStore.reports"
      :total="listStore.total"
      :current-page="Number(filters.page)"
      :page-size="Number(filters.pageSize)"
      @view="goToReport"
      @page-change="onPageChange"
    />
  </div>
</template>

<script setup lang="ts">
/**
 * Bug 1 修复集成点：
 *
 * 此组件的筛选状态完全由 useRouteQuery 驱动，不使用本地 ref 存储筛选值。
 * - filters 是从 route.query 派生的 computed
 * - updateFilters 通过 router.push 更新 URL（创建新历史条目）
 * - 浏览器返回时，URL恢复 → route.query 更新 → filters 重新计算 → watch 触发重新请求
 *
 * 导航到详情页使用 router.push（非 replace），确保历史栈正确。
 */
import { watch, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useReportListStore } from '@/stores/reportList'
import { useRouteQuery } from '@/composables/useRouteQuery'
import ReportFilters from '@/components/ReportFilters.vue'
import ReportTable from '@/components/ReportTable.vue'

const router = useRouter()
const route = useRoute()
const listStore = useReportListStore()

// Bug 1 核心：筛选状态从 route.query 派生
const { filters, updateFilters, resetFilters } = useRouteQuery({
  status: '',
  page: '1',
  keyword: '',
  pageSize: '20'
})

// 当 URL query 变化时自动重新获取数据
watch(filters, () => {
  fetchData()
}, { immediate: true })

function fetchData() {
  listStore.fetchReports(filters.value)
}

// Bug 1 关键：使用 router.push 导航，保留当前列表页的历史记录
function goToReport(id: string) {
  router.push({ name: 'report-detail', params: { id } })
}

function onPageChange(page: string) {
  updateFilters({ page })
}

// 如果从详情页重定向回来且带有错误参数，显示提示
const errorMessage = computed(() => {
  if (route.query.error === 'report-not-found') {
    return `报告 #${route.query.failedId} 未找到`
  }
  return null
})
</script>

<style scoped>
.report-list-view {
  max-width: 1080px;
  margin: 0 auto;
  padding: 24px;
}

.report-list-view h1 {
  font-size: 22px;
  margin: 0 0 20px;
  color: #111827;
}

.error-toast {
  padding: 12px 16px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #991b1b;
  font-size: 14px;
  margin-bottom: 16px;
}

.loading-hint {
  text-align: center;
  padding: 48px;
  color: #6b7280;
}

.error-hint {
  text-align: center;
  padding: 48px;
  color: #dc2626;
}

.error-hint button {
  margin-left: 12px;
  padding: 4px 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: white;
  cursor: pointer;
}
</style>
