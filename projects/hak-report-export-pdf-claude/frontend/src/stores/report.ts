import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Report } from '@/types/report'
import { getReport, submitReview } from '@/api/reports'
import type { ReviewPayload } from '@/types/report'

export const useReportStore = defineStore('report', () => {
  const currentReport = ref<Report | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchReport(id: string) {
    loading.value = true
    error.value = null
    try {
      const data = await getReport(id)
      currentReport.value = data
      // 防御性备份：将报告ID存入sessionStorage，用于异常恢复
      sessionStorage.setItem('lastReportId', id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '加载报告失败'
      throw e // 重新抛出，让路由守卫可以捕获
    } finally {
      loading.value = false
    }
  }

  async function review(id: string, payload: ReviewPayload) {
    loading.value = true
    error.value = null
    try {
      const data = await submitReview(id, payload)
      currentReport.value = data
      return data
    } catch (e) {
      error.value = e instanceof Error ? e.message : '提交审核失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function setLoading(val: boolean) {
    loading.value = val
  }

  function $reset() {
    currentReport.value = null
    loading.value = false
    error.value = null
  }

  return { currentReport, loading, error, fetchReport, review, setLoading, $reset }
})
