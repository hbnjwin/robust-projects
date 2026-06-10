import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/reports',
    name: 'ReportList',
    component: () => import('@/views/ReportList.vue'),
  },
  {
    path: '/reports/:id/review',
    name: 'ReportReview',
    component: () => import('@/views/ReportReview.vue'),
    // Mark as cacheable for keep-alive
    meta: { keepAlive: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
