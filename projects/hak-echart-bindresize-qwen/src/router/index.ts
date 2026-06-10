import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/statistics'
  },
  {
    path: '/statistics',
    name: 'Statistics',
    component: () => import('@/views/StatisticsPanel.vue'),
    meta: {
      title: '审核统计',
      icon: 'DataLine',
      keepAlive: true // 统计面板使用 keep-alive 缓存
    }
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/views/ReportList.vue'),
    meta: {
      title: '报告列表',
      icon: 'Document',
      keepAlive: false
    }
  },
  {
    path: '/devices',
    name: 'Devices',
    component: () => import('@/views/DeviceMonitoring.vue'),
    meta: {
      title: '设备监控',
      icon: 'Monitor',
      keepAlive: false
    }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
