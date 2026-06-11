export default [
	{
		path: '/login',
		name: 'Login',
		component: () => import('@/pages/login/index.vue'),
		meta: { title: '登录', auth: 'Login' }
	}
]
