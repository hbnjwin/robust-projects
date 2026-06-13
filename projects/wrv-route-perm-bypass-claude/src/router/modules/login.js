export default [
    {
        path: '/login',
        name: 'Login',
        auth: 'Login',
        hidden: true,
        hiddenChildren: true,
        component: () => import('@/pages/login/index.vue'),
        meta: { title: '登录页', auth: 'Login' }
    }
]