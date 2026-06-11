import { createRouter, createWebHashHistory } from 'vue-router'
import nprogress from 'nprogress'
import oauth2 from '@/utils/oauth2'

import LoginRoute from './modules/auth-center'

const routerModules = [
	LoginRoute,
	[
		{
			path: '/',
			name: 'Home',
			component: () => import('@/pages/home/index.vue'),
			meta: { title: '首页' }
		},
		{
			path: '/404',
			name: '404',
			hidden: true,
			component: () => import('@/pages/not-found/index.vue'),
			meta: { title: '404' }
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

router.beforeEach(async (to, from, next) => {
	nprogress.start()
	if (to.name === 'Login') {
		nprogress.done()
		return next()
	}
	if (!oauth2.getOauth()) {
		nprogress.done()
		return next({ name: 'Login', replace: true })
	}
	if (!to.name) {
		nprogress.done()
		return next({ name: '404', replace: true })
	}
	nprogress.done()
	return next()
})

export default router
