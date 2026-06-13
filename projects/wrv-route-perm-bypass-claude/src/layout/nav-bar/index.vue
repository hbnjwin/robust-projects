<template>
	<div class="app-header">
		<PlatformLogo />
		<div class="tabs">
			<t-head-menu theme="light" v-model="defaultMenu" :defaultValue="defaultMenu" expandType="popup" @change="changeHandler">
				<menu-item v-for="menu in routes" :key="menu.auth" :menu="menu" />
			</t-head-menu>
		</div>
		<div class="flex-start">
			<t-popup
				trigger="hover"
				overlayInnerClassName="popup-no-padding"
				:overlayInnerStyle="{ marginRight: '0px', minWidth: '100px' }"
				:showArrow="true"
				placement="bottom-right"
			>
				<template #content>
					<t-divider style="margin: 15px 0"></t-divider>
					<div class="logout" @click="handleCommand('logout')">退出登录</div>
				</template>
				<t-space align="center" size="4px">
					<img :src="avater" width="32px" height="32px" alt="" />
					<div m-l-5px>{{ userInfo.operatorName }}</div>
					<i class="iconfont icon-xiala" text="16px" m-r-5px></i>
				</t-space>
			</t-popup>
		</div>
	</div>
</template>

<script setup>
import oauth2 from '@/utils/oauth2'
import MenuItem from './components/menu-item.vue'
import PlatformLogo from './components/platform-logo.vue'
import avater from '@/assets/image/logo/avatar.png'
import { useUserinfoStore } from '@/store/modules/userinfo'

const { userInfo } = storeToRefs(useUserinfoStore())
const router = useRouter()
const route = useRoute()
const routes = computed(() => {
	const menus = userInfo.value?.menus || []
	// 递归处理路由，过滤掉hidden为true的项和无权限的项，并处理其子路由
	const filterRoutes = (routeList) => {
		return (
			routeList
				.filter((item) => !item.hidden && (!item.auth || menus.includes(item.auth))) // 过滤hidden和无权限的路由
				.map((item) => {
					// 如果有子路由，递归处理子路由
					if (item.children && item.children.length > 0) {
						return {
							...item,
							children: filterRoutes(item.children) // 递归处理子路由
						}
					}
					return item
				})
				// 过滤掉子路由为空的项（如果需要保留没有子路由的父项，可去掉此过滤）
				.filter((item) => !(item.children && item.children.length === 0))
		)
	}

	return filterRoutes(router.options.routes)
})

const defaultMenu = ref(route.meta.auth)

onMounted(() => {})

const handleCommand = (value) => {
	switch (value) {
		case 'logout':
			signOut()
			break
		default:
			break
	}
}

const signOut = () => {
	router.push({ name: 'Login' })
	oauth2.remove()
	userInfo.value = null
	localStorage.clear()
}

const changeHandler = (active) => {
	defaultMenu.value = active
}
</script>

<style lang="less" scoped>
.app-header {
	width: 100vw;
	height: 60px;
	display: flex;
	align-items: space-between;
	padding: 0 18px;
	background: linear-gradient(180deg, #dee8fd 0%, #e1f2fd 13.45%, #f6f7fe 100%);
	background-size: 100% 100%;
}
.logout {
	width: 100%;
	text-align: center;
	padding-bottom: 15px;
	cursor: pointer;
	color: var(--text-color-1);
	&:hover {
		color: var(--td-error-color-4);
	}
}
.tabs {
	display: flex;
	align-items: center;
	padding-left: 12px;
	margin: 0 auto;
}
:deep(.t-head-menu) {
	background-color: transparent;
}
:deep(.t-menu__item.t-is-active) {
	color: #fff;
	background: linear-gradient(to right, #2671fe, #65a9f7);
	border-radius: 12px;
}
</style>
