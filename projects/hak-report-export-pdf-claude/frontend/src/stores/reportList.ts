import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Report, ReportListFilters } from '@/types/report'
import { getReports } from '@/api/reports'

/**
 * 列表数据Store —— 只存列表数据，不存筛选状态。
 * 筛选状态由URL query参数驱动（见 useRouteQuery composable），
 * 这是修复Bug 1（浏览器返回时query参数丢失）的关键设计。
 */
export const useReportListStore = defineStore('reportList', () => {
  const reports = ref<Report[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchReports(filters: ReportListFilters) {
    loading.value = true
    error.value = null
    try {
      const result = await getReports(filters)
      reports.value = result.items
      total.value = result.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载报告列表失败'
    } finally {
      loading.value = false
    }
  }

  function $reset() {
    reports.value = []
    total.value = 0
    loading.value = false
    error.value = null
  }

  return { reports, total, loading, error, fetchReports, $reset }
})
