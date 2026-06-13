import Layout from '@/layout/index.vue'

export default [
	{
		path: '/system',
		auth: 'System',
		name: 'System',
		redirect: { name: 'Rulebase' },
		component: Layout,
		label: '系统管理',
		children: [
			{
				path: 'rulebase',
				auth: 'Rulebase',
				name: 'Rulebase',
				component: () => import('@/pages/system/rulebase/index.vue'),
				label: '要索提取规则库',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '要索提取规则库', auth: 'Rulebase' }
			},
            {
				path: 'management',
				auth: 'Management',
				name: 'Management',
				component: () => import('@/pages/system/management/index.vue'),
				label: '后台管理',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '后台管理', auth: 'Management' }
			}
		]
	},
]
