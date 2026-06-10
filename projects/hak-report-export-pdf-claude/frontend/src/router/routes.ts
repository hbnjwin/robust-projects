import type { RouteRecordRaw } from 'vue-router'
import { reportDataGuard } from './guards'
import { lazyView } from '@/composables/useAsyncRoute'

/**
 * 三层嵌套路由结构：
 *   /reports                     → 报告列表（Level 1）
 *   /reports/:id                 → 报告详情布局（Level 2，含beforeEnter守卫）
 *     /reports/:id/              → 报告详情内容（Level 2 默认子路由）
 *     /reports/:id/review        → 报告审核页面（Level 3）
 *
 * Bug修复要点：
 * - lazyView() 包装懒加载（修复Bug 3：组件加载闪烁）
 * - beforeEnter: reportDataGuard 在父路由（修复Bug 2：F5刷新白屏）
 * - 列表页通过 useRouteQuery 驱动筛选（修复Bug 1：返回丢失query参数）
 */
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/reports'
  },
  {
    path: '/reports',
    name: 'report-list',
    component: lazyView(() => import('@/views/ReportListView.vue'))
  },
  {
    path: '/reports/:id',
    // 布局组件：包含 <RouterView> 供子路由渲染
    component: lazyView(() => import('@/views/ReportDetailLayout.vue')),
    // Bug 2 修复：beforeEnter 守卫确保进入前 store 有数据
    // 刷新时 store 为空，守卫会先 await fetchReport 再放行
    beforeEnter: reportDataGuard,
    children: [
      {
        path: '',
        name: 'report-detail',
        component: lazyView(() => import('@/views/ReportDetailView.vue'))
      },
      {
        path: 'review',
        name: 'report-review',
        component: lazyView(() => import('@/views/ReportReviewView.vue'))
      }
    ]
  }
]
