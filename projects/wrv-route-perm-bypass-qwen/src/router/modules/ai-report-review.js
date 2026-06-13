import Layout from '@/layout/index.vue'

export default [
	{
		path: '/ai-report-review',
		auth: 'AiReport',
		name: 'AiReport',
		redirect: { name: 'AiReportReview' },
		component: Layout,
		label: 'AI 报告审核',
		children: [
			{
				path: 'index',
				auth: 'AiReportReview',
				name: 'AiReportReview',
				component: () => import('@/pages/ai-report-review/index.vue'),
				label: 'AI 报告审核',
				hidden: false,
				hiddenChildren: true,
				meta: { title: 'AI 报告审核', auth: 'AiReport' }
			}
		]
	},
]
