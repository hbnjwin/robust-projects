<template>
	<div class="login-page">
		<div class="login-form">
			<h2>风控报告审核系统</h2>
			<el-form :model="form" label-width="0">
				<el-form-item>
					<el-input v-model="form.username" placeholder="请输入用户名" />
				</el-form-item>
				<el-form-item>
					<el-input v-model="form.password" type="password" placeholder="请输入密码" />
				</el-form-item>
				<el-form-item>
					<el-button type="primary" style="width: 100%" @click="handleLogin">登录</el-button>
				</el-form-item>
			</el-form>
		</div>
	</div>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserinfoStore } from '@/store/modules/userinfo'
import oauth2 from '@/utils/oauth2'

const router = useRouter()
const userinfoStore = useUserinfoStore()

const form = reactive({
	username: '',
	password: ''
})

async function handleLogin() {
	// 模拟登录
	oauth2.setOauth('mock-token-123')
	userinfoStore.setUserInfo({
		operatorName: form.username,
		operatorId: '1001'
	})
	router.push({ name: 'Home' })
}
</script>

<style scoped>
.login-page {
	display: flex;
	justify-content: center;
	align-items: center;
	height: 100vh;
	background: #f0f2f5;
}

.login-form {
	width: 400px;
	padding: 40px;
	background: #fff;
	border-radius: 8px;
	box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
</style>
