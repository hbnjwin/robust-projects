import router from './router'
import { getAccessToken } from './auth'

// 不需要登录的白名单路由
const whiteList = [
  '/login',
  '/register',
  '/portal',        // BUG: 只匹配了 /portal 精确路径
  '/portal/index',  // 只匹配了 /portal/index
  // BUG: 没有匹配 /portal/courses/:id, /portal/news/:id 等带参数的子路由
  // /portal/courses/123 不在白名单中，会被重定向到 /portal/index
]

router.beforeEach(async (to, from, next) => {
  const token = getAccessToken()

  if (token) {
    if (to.path === '/login') {
      next({ path: '/' })
    } else {
      next()
    }
  } else {
    // BUG: 白名单匹配用的是精确匹配 includes
    // /portal/courses/123 不在 whiteList 数组中
    // 应该用 startsWith('/portal') 来匹配所有 /portal 开头的路由
    if (whiteList.includes(to.path)) {
      next()
    } else {
      // 未登录且不在白名单 → 重定向
      // BUG: 门户页面不需要登录但被重定向到了首页
      next(`/portal/index?redirect=${to.fullPath}`)
    }
  }
})
