import RouterView from '@/layout/router-view.vue'
export default [
	{
		path: '/auth',
		name: 'Auth',
		component: RouterView,
		redirect: {
			name: 'Auth.Send'
		},
		meta: { hidden: true, title: '权限', hiddenChildren: true, sort: 10 },
		children: [
			{
				path: 's',
				name: 'Auth.Send',
				component: () => import('@/pages/auth-center/send.vue')
			},
			{
				path: 'r',
				name: 'Auth.Receive',
				component: () => import('@/pages/auth-center/receive.vue')
			}
		]
	}
]
