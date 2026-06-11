import Layout from '@/layout/index.vue'

export default [
	{
		path: '/',
		auth: 'Expert',
		name: 'Expert',
		redirect: { name: 'ExpertDatabase' },
		component: Layout,
		label: '报告专家库',
		children: [
			{
				path: 'expert-database',
				auth: 'ExpertDatabase',
				name: 'ExpertDatabase',
				component: () => import('@/pages/expert-database/index.vue'),
				label: '报告专家库',
				hidden: false,
				hiddenChildren: false,
				meta: { title: '报告专家库', auth: 'Expert' }
			},
			{
				path: 'expert-database-view',
				auth: 'ExpertDatabaseView',
				name: 'ExpertDatabaseView',
				component: () => import('@/pages/expert-database/view.vue'),
				label: '报告专家库-查看',
				hidden: true,
				hiddenChildren: true,
				meta: { title: '报告专家库-查看', auth: 'Expert' }
			}
		]
	}
]
