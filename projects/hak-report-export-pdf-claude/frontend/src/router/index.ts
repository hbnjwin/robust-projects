import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes,
  /**
   * scrollBehavior 配合 Bug 1 修复：
   * 浏览器返回时，不仅URL的query参数恢复，滚动位置也恢复到之前的位置。
   */
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  }
})

export default router
