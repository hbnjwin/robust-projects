import { defineStore } from 'pinia'
import { RouteRecordRaw } from 'vue-router'
import router from './router'

interface PermissionState {
  routes: RouteRecordRaw[]
  addRoutes: RouteRecordRaw[]
  isAddRouters: boolean
}

function filterAsyncRoutes(menus: any[]): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = []
  menus.forEach((menu) => {
    const route: RouteRecordRaw = {
      path: menu.path,
      name: menu.componentName,
      component: () => import(`../views/${menu.component}.vue`),
      meta: { title: menu.name, icon: menu.icon }
    }
    if (menu.children?.length) {
      route.children = filterAsyncRoutes(menu.children)
    }
    routes.push(route)
  })
  return routes
}

export const usePermissionStore = defineStore('permission', {
  state: (): PermissionState => ({
    routes: [],
    addRoutes: [],
    isAddRouters: false
  }),

  actions: {
    async generateRoutes(roleId: number) {
      const res = await fetch(`/api/system/auth/menu-list?roleId=${roleId}`)
      const { data: menus } = await res.json()
      const accessedRoutes = filterAsyncRoutes(menus)

      // BUG: 角色切换时没有先移除旧的动态路由
      // router.removeRoute() 没有被调用
      // 导致旧角色的路由还在，新角色的路由重复添加
      // Vue Router 会报 "Duplicate named routes" 警告，严重时白屏

      accessedRoutes.forEach((route) => {
        router.addRoute(route)  // BUG: 重复添加同名路由
      })

      this.addRoutes = accessedRoutes
      this.routes = [...this.routes, ...accessedRoutes]  // BUG: routes 也是追加不是替换
      this.isAddRouters = true
    },

    resetRoutes() {
      // 这个方法存在但从未在角色切换时被调用
      this.addRoutes.forEach((route) => {
        if (route.name) {
          router.removeRoute(route.name)
        }
      })
      this.addRoutes = []
      this.routes = []
      this.isAddRouters = false
    }
  }
})
