export default [
  { path: '/auth/s', component: () => import('@/pages/auth-center/send.vue') },
  { path: '/auth/r', component: () => import('@/pages/auth-center/receive.vue') },
]
