import { createRouter, createWebHistory } from 'vue-router'
import { useReportStore } from '@/store/report'
import ReportList from '@/views/ReportList.vue'

// Bug 3 修复：defineAsyncComponent 配 loadingComponent 防止闪烁
import { defineAsyncComponent } from 'vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

const ReportDetail = defineAsyncComponent({
  loader: () => import('@/views/ReportDetail.vue'),
  loadingComponent: LoadingSpinner,
  delay: 0, // 立即显示 loading，避免闪烁
  timeout: 10000
})

const ReviewPage = defineAsyncComponent({
  loader: () => import('@/views/ReviewPage.vue'),
  loadingComponent: LoadingSpinner,
  delay: 0,
  timeout: 10000
})

const routes = [
  {
    path: '/',
    redirect: '/reports'
  },
  {
    path: '/reports',
    name: 'ReportList',
    component: ReportList,
    // Bug 1 修复：保留 query 参数的关键配置
    props: route => ({
      status: route.query.status || '',
      page: parseInt(route.query.page) || 1,
      keyword: route.query.keyword || ''
    })
  },
  {
    path: '/reports/:id',
    name: 'ReportDetail',
    component: ReportDetail,
    props: true,
    children: [
      {
        path: 'review',
        name: 'ReviewPage',
        component: ReviewPage,
        props: true,
        // Bug 2 修复：路由守卫在刷新时正确处理 store 为空的情况
        beforeEnter: async (to, from, next) => {
          const store = useReportStore()

          // 刷新后 store 被清空，需要先加载数据
          if (!store.reports || store.reports.length === 0) {
            try {
              await store.loadReports()
              // 数据加载成功后继续导航
              next()
            } catch (error) {
              console.error('加载报告数据失败:', error)
              // 加载失败时重定向到列表页
              next('/reports')
            }
          } else {
            // store 有数据，直接继续
            next()
          }
        }
      }
    ],
    beforeEnter: async (to, from, next) => {
      const store = useReportStore()

      // Bug 2 修复：同样在第二层路由检查并加载数据
      if (!store.reports || store.reports.length === 0) {
        try {
          await store.loadReports()
          next()
        } catch (error) {
          console.error('加载报告数据失败:', error)
          next('/reports')
        }
      } else {
        next()
      }
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  // Bug 1 修复：自定义 scrollBehavior 保留滚动位置和 query 参数
  scrollBehavior(to, from, savedPosition) {
    // 如果有保存的位置（浏览器前进/后退），恢复到之前的位置
    if (savedPosition) {
      return savedPosition
    }
    // 否则滚动到顶部
    return { top: 0 }
  }
})

// 全局路由守卫：确保刷新时数据加载
router.beforeEach(async (to, from, next) => {
  // 只在首次加载或刷新时执行
  if (to.name !== 'ReportList') {
    const store = useReportStore()

    // 如果 store 为空且目标是详情或审核页，先加载数据
    if ((!store.reports || store.reports.length === 0) && to.params.id) {
      try {
        await store.loadReports()
      } catch (error) {
        console.error('路由守卫：加载数据失败', error)
      }
    }
  }

  next()
})

export default router
