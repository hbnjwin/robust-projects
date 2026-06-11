import Layout from '@/layout/index.vue'
import RouterView from '@/layout/router-view.vue'

export default [
	{
		path: '/',
		auth: 'Home',
		name: 'Home',
		redirect: { name: 'Home.CreateReview' }, // 重定向到子路由
		component: Layout,
		label: '主页',
		children: [
			{
				path: 'create-review',
				auth: 'Home.CreateReview',
				name: 'Home.CreateReview',
				redirect: { name: 'Home.CreateReview.Index' },
				component: RouterView,
				label: '创建评审计划',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '创建评审计划', auth: 'Home.CreateReview' },
				children: [
					{
						path: 'index',
						auth: 'Home.CreateReview',
						name: 'Home.CreateReview.Index',
						component: () => import('@/pages/home/create-review/index.vue'),
						label: '创建评审计划',
						hidden: true,
						hiddenChildren: true,
						meta: { title: '创建评审计划', auth: 'Home.CreateReview' }
					},
					{
						path: 'create',
						auth: 'Home.CreateReview.Create',
						name: 'Home.CreateReview.Create',
						component: () => import('@/pages/home/create-review/create.vue'),
						label: '创建评审计划新增',
						hidden: true,
						hiddenChildren: true,
						meta: { title: '创建评审计划新增', auth: 'Home.CreateReview' }
					}
				]
			},
			{
				path: 'allocation-review',
				auth: 'Home.AllocationReview',
				name: 'Home.AllocationReview',
				redirect: { name: 'Home.AllocationReview.Index' },
				component: RouterView,
				label: '分配审核任务',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '分配审核任务', auth: 'Home.AllocationReview' },
				children: [
					{
						path: 'index',
						auth: 'Home.AllocationReview',
						name: 'Home.AllocationReview.Index',
						component: () => import('@/pages/home/allocation-review/index.vue'),
						label: '分配审核任务',
						hidden: true,
						hiddenChildren: true,
						meta: { title: '分配审核任务', auth: 'Home.AllocationReview' }
					},
					{
						path: 'create',
						auth: 'Home.AllocationReview.Create',
						name: 'Home.AllocationReview.Create',
						component: () => import('@/pages/home/allocation-review/create.vue'),
						label: '分配审核任务新增',
						hidden: true,
						hiddenChildren: true,
						meta: { title: '分配审核任务新增', auth: 'Home.AllocationReview' }
					}
				]
			},
			{
				path: 'data-upload',
				auth: 'Home.DataUpload',
				name: 'Home.DataUpload',
				redirect: { name: 'Home.DataUpload.Index' },
				component: RouterView,
				label: '资料上传',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '资料上传', auth: 'Home.DataUpload' },
				children: [
					{
						path: 'index',
						auth: 'Home.DataUpload',
						name: 'Home.DataUpload.Index',
						component: () => import('@/pages/home/data-upload/index.vue'),
						label: '资料上传',
						hidden: true,
						hiddenChildren: true,
						meta: { title: '资料上传', auth: 'Home.DataUpload' }
					},
					{
						path: 'edit',
						auth: 'Home.DataUpload.Edit',
						name: 'Home.DataUpload.Edit',
						component: () => import('@/pages/home/data-upload/edit.vue'),
						label: '分配审核任务编辑',
						hidden: true,
						hiddenChildren: true,
						meta: { title: '分配审核任务编辑', auth: 'Home.DataUpload' }
					}
				]
			},
			{
				path: 'document-prereview',
				auth: 'Home.DocumentPrereview',
				name: 'Home.DocumentPrereview',
				component: () => import('@/pages/home/document-prereview/index.vue'),
				label: '文档预审',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '文档预审', auth: 'Home.DocumentPrereview' }
			},
			{
				path: 'report-prereview',
				auth: 'Home.ReportPrereview',
				name: 'Home.ReportPrereview',
				component: () => import('@/pages/home/report-prereview/index.vue'),
				label: '报告预审',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '报告预审', auth: 'Home.ReportPrereview' }
			},
			{
				path: 'report-substantive-examination',
				auth: 'Home.ReportSubstantiveExamination',
				name: 'Home.ReportSubstantiveExamination',
				component: () => import('@/pages/home/report-substantive-examination/index.vue'),
				label: '报告实审',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '报告实审', auth: 'Home.ReportSubstantiveExamination' }
			},
			{
				path: 'opinion-generation',
				auth: 'Home.OpinionGeneration',
				name: 'Home.OpinionGeneration',
				component: () => import('@/pages/home/opinion-generation/index.vue'),
				label: '评审意见生成',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '评审意见生成', auth: 'Home.OpinionGeneration' }
			},
			{
				path: 'archive',
				auth: 'Home.Archive',
				name: 'Home.Archive',
				component: () => import('@/pages/home/archive/index.vue'),
				label: '归档',
				hidden: false,
				hiddenChildren: true,
				meta: { title: '归档', auth: 'Home.Archive' }
			}
		]
	}
]
