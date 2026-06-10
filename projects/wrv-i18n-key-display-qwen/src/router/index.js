import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/LoginView.vue')
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/dashboard/DashboardView.vue')
      },
      {
        path: 'users',
        name: 'UserList',
        component: () => import('../views/user/UserListView.vue')
      },
      {
        path: 'roles',
        name: 'RoleList',
        component: () => import('../views/role/RoleListView.vue')
      },
      {
        path: 'logs',
        name: 'LogList',
        component: () => import('../views/log/LogListView.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('../views/settings/SettingsView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
