import { createRouter, createWebHashHistory } from 'vue-router'
import nprogress from 'nprogress'
import oauth2 from '@/utils/oauth2'
import { useUserinfoStore } from '@/store/modules/userinfo'

import LoginRoute from './modules/login'
import ExpertDatabaseRoute from './modules/expert-database'
import AiReportReviewRoute from './modules/ai-report-review'
import SystemRoute from './modules/system'

const routerModules = [
	LoginRoute,
	ExpertDatabaseRoute,
	AiReportReviewRoute,
	SystemRoute,
	[
		{
			path: '/404',
			name: '404',
			auth: '404',
			hidden: true,
			hiddenChildren: true,
			component: () => import('@/pages/not-found/index.vue'),
			meta: { title: '404', auth: '404' }
		},
		{
			path: '/403',
			name: '403',
			auth: '403',
			hidden: true,
			hiddenChildren: true,
			component: () => import('@/pages/no-permission/index.vue'),
			meta: { title: '403', auth: '403' }
		}
	]
]

const routes = []
for (const [, modules] of Object.entries(routerModules)) {
	const values = Object.values(modules).flat(1)
	routes.push(...values)
}

const router = createRouter({
	history: createWebHashHistory(),
	routes: routes
})
// 全局的路由拦截
const baseRouterNames = ['403', '404', 'Login']

router.beforeEach(async (to, from, next) => {
	nprogress.start()
	// 可以直接访问
	if (baseRouterNames.includes(to.name)) {
		return next()
	}
	// 没有登录
	if (to.name !== 'Login' && !oauth2.getOauth()) {
		nprogress.done()
		return next({ name: 'Login', replace: true })
	}
	if (!to.name) {
		nprogress.done()
		return next({ name: '404', replace: true })
	}
	// 权限校验
	const { userInfo } = useUserinfoStore()
	const menus = userInfo?.menus || []
	if (to.meta?.auth && !menus.includes(to.meta.auth)) {
		nprogress.done()
		return next({ name: '403', replace: true })
	}
	nprogress.done()
	return next()
})
export default router
