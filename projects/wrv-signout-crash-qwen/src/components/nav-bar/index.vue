<template>
	<div class="nav-bar">
		<div class="nav-bar__logo">
			<img src="" alt="logo" />
			<span>风控报告审核系统</span>
		</div>
		<div class="nav-bar__right">
			<div class="nav-bar__user">
				<el-dropdown>
					<span class="el-dropdown-link">
						{{ userInfo.operatorName }}
						<el-icon class="el-icon--right"><arrow-down /></el-icon>
					</span>
					<template #dropdown>
						<el-dropdown-menu>
							<el-dropdown-item @click="goProfile">个人中心</el-dropdown-item>
							<el-dropdown-item @click="signOut">退出登录</el-dropdown-item>
						</el-dropdown-menu>
					</template>
				</el-dropdown>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { useUserinfoStore } from '@/store/modules/userinfo'
import oauth2 from '@/utils/oauth2'

const router = useRouter()
const userinfoStore = useUserinfoStore()

const userInfo = computed(() => userinfoStore.userInfo)

function goProfile() {
	router.push({ name: 'Profile' })
}

async function signOut() {
	userinfoStore.clearUserInfo()
	oauth2.removeOauth()
	await router.push({ name: 'Login' })
}
</script>

<style scoped>
.nav-bar {
	display: flex;
	justify-content: space-between;
	align-items: center;
	height: 56px;
	padding: 0 20px;
	background: #fff;
	box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.nav-bar__logo {
	display: flex;
	align-items: center;
	gap: 8px;
	font-size: 16px;
	font-weight: 600;
}

.nav-bar__right {
	display: flex;
	align-items: center;
}

.el-dropdown-link {
	cursor: pointer;
	display: flex;
	align-items: center;
}
</style>
