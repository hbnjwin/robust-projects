import { createRouter, createWebHashHistory } from 'vue-router'
import { getOauth } from '@/utils/oauth2'
import LoginRoute from './modules/login'
import ExpertDatabaseRoute from './modules/expert-database'
import AiReportReviewRoute from './modules/ai-report-review'
import SystemRoute from './modules/system'

const routes = [
  ...LoginRoute,
  ...ExpertDatabaseRoute,
  ...AiReportReviewRoute,
  ...SystemRoute,
  { path: '/404', component: () => import('@/pages/not-found/index.vue') },
  { path: '/403', component: () => import('@/pages/no-permission/index.vue') },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to, from, next) => {
  if (to.path === '/login') return next()
  if (!getOauth()) return next('/login')
  next()
})

export default router
