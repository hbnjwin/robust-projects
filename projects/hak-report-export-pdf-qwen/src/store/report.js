import { defineStore } from 'pinia'

const STORAGE_KEY = 'report_store_data'

// Bug 2 修复：使用 sessionStorage 持久化 store 数据，防止刷新后数据丢失
function saveToStorage(state) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      reports: state.reports,
      currentReport: state.currentReport,
      timestamp: Date.now()
    }))
  } catch (e) {
    console.warn('保存 store 到 sessionStorage 失败:', e)
  }
}

function loadFromStorage() {
  try {
    const data = sessionStorage.getItem(STORAGE_KEY)
    if (!data) return null

    const parsed = JSON.parse(data)

    // 可选：检查数据是否过期（比如 30 分钟）
    const MAX_AGE = 30 * 60 * 1000
    if (Date.now() - parsed.timestamp > MAX_AGE) {
      sessionStorage.removeItem(STORAGE_KEY)
      return null
    }

    return parsed
  } catch (e) {
    console.warn('从 sessionStorage 加载 store 失败:', e)
    return null
  }
}

export const useReportStore = defineStore('report', {
  state: () => {
    // Bug 2 修复：初始化时尝试从 sessionStorage 恢复数据
    const cached = loadFromStorage()

    return {
      reports: cached?.reports || [],
      currentReport: cached?.currentReport || null,
      loading: false,
      error: null
    }
  },

  getters: {
    getReportById: (state) => {
      return (id) => state.reports.find(r => r.id === id)
    },

    isLoaded: (state) => {
      return state.reports.length > 0
    }
  },

  actions: {
    async loadReports() {
      // 避免重复加载
      if (this.loading) return
      if (this.reports.length > 0) return

      this.loading = true
      this.error = null

      try {
        // 模拟 API 调用
        const response = await fetch('/api/reports')
        const data = await response.json()

        this.reports = data.reports || data

        // Bug 2 修复：数据加载成功后保存到 sessionStorage
        saveToStorage(this)
      } catch (error) {
        this.error = error.message || '加载报告失败'
        console.error('加载报告失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    async loadReportById(id) {
      if (this.loading) return

      // 先从已加载的报告中查找
      const existing = this.getReportById(id)
      if (existing) {
        this.currentReport = existing
        return existing
      }

      this.loading = true
      this.error = null

      try {
        const response = await fetch(`/api/reports/${id}`)
        const data = await response.json()

        this.currentReport = data

        // 如果报告中没有 id，添加上
        if (!data.id) {
          data.id = id
        }

        // 添加到报告列表（如果不存在）
        if (!this.getReportById(id)) {
          this.reports.push(data)
        }

        // 保存到 sessionStorage
        saveToStorage(this)

        return data
      } catch (error) {
        this.error = error.message || '加载报告详情失败'
        console.error('加载报告详情失败:', error)
        throw error
      } finally {
        this.loading = false
      }
    },

    setCurrentReport(report) {
      this.currentReport = report
      saveToStorage(this)
    },

    clearCurrentReport() {
      this.currentReport = null
      saveToStorage(this)
    },

    clearAll() {
      this.reports = []
      this.currentReport = null
      this.error = null
      sessionStorage.removeItem(STORAGE_KEY)
    }
  }
})
