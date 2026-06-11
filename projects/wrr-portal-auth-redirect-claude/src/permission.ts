import router from './router'
import { getAccessToken } from './auth'

// 不需要登录的白名单路由
const whiteList = [
  '/login',
  '/register',
  '/portal',
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
    if (whiteList.some(p => to.path === p || to.path.startsWith(p + '/'))) {
      next()
    } else {
      next(`/portal/index?redirect=${to.fullPath}`)
    }
  }
})
