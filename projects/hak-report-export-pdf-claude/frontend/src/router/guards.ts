import type { NavigationGuardWithThis } from 'vue-router'
import { useReportStore } from '@/stores/report'

/**
 * Bug 2 核心修复：reportDataGuard
 *
 * 解决"审核页F5刷新白屏"的问题。
 *
 * 挂载在 /reports/:id 父路由的 beforeEnter 上。
 * Vue Router 4 的 beforeEnter 在从外部进入该路由时触发（包括F5刷新、直接URL访问），
 * 但在其子路由之间导航时不会重复触发。
 *
 * 逻辑：
 * 1. store已有匹配报告 → 直接放行（正常导航场景）
 * 2. store为空 → await API获取数据后放行（F5刷新/直接访问场景）
 * 3. API失败 → 重定向到列表页并携带错误信息
 */
export const reportDataGuard: NavigationGuardWithThis<undefined> = async (to) => {
  const store = useReportStore()
  const id = to.params.id as string

  // Case 1: Store已有该报告数据（正常从列表页点击进入）
  if (store.currentReport && store.currentReport.id === id) {
    return true
  }

  // Case 2 & 3: Store为空（F5刷新、直接URL访问、deeplink）
  try {
    store.setLoading(true)
    await store.fetchReport(id)
    return true
  } catch {
    // API失败，重定向到列表页并提示错误
    return {
      name: 'report-list',
      query: { error: 'report-not-found', failedId: id }
    }
  }
}
