import router from './router'
import { getAccessToken } from './auth'

// 不需要登录的白名单路由（精确匹配）
const whiteList = [
  '/login',
  '/register',
]

// 判断路径是否属于门户公开页面（/portal 及其所有子路由）
function isPortalRoute(path: string): boolean {
  return path === '/portal' || path.startsWith('/portal/')
}

router.beforeEach(async (to, from, next) => {
  const token = getAccessToken()

  if (token) {
    if (to.path === '/login') {
      next({ path: '/' })
    } else {
      next()
    }
  } else {
    if (whiteList.includes(to.path) || isPortalRoute(to.path)) {
      next()
    } else {
      next(`/portal/index?redirect=${to.fullPath}`)
    }
  }
})
