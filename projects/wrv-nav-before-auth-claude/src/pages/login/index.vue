<template>
	<div class="login-wrapper">
		<img class="login-logo" src="@/assets/image/logo/linkyoyo.png" alt="" />
		<div class="flex-start">
			<img src="@/assets/image/login-logo/登录页机器人插画.png" style="width: 600px" alt="" />
			<div>
				<div class="login-title">金风AI报告审核</div>
				<div class="login-tabs">
					<div class="top">
						<div class="top-right top-common">
							<i class="iconfont icon-zhanghao" m-r-5px></i>
							<span>账号登录</span>
						</div>
					</div>
				</div>
				<div class="login-main">
					<t-form :data="formData" :rules="rules" labelAlign="top" ref="form" label-width="80px" @submit="handleLogin">
						<t-form-item label="账号" name="userName">
							<t-input v-model="formData.userName" placeholder="请输入账号">
								<template #prefix-icon>
									<i class="iconfont icon-zhanghao" style="color: #ddd"></i>
								</template>
							</t-input>
						</t-form-item>
						<t-form-item label="密码" name="password">
							<t-input type="password" v-model="formData.password" placeholder="请输入密码">
								<template #prefix-icon>
									<i class="iconfont icon-mima1" style="color: #ddd"></i>
								</template>
							</t-input>
						</t-form-item>
						<t-form-item>
							<div style="width: 100%" m-t-20px>
								<t-button theme="primary" type="submit" :loading="loading" style="width: 100%">登录</t-button>
							</div>
						</t-form-item>
					</t-form>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import oauth2 from '@/utils/oauth2'
import { AUTH_CENTER } from '@/api'
import CryptoJS from 'crypto-js'
import { MessagePlugin } from 'tdesign-vue-next'
import { useUserinfoStore } from '@/store/modules/userinfo'

const router = useRouter()
const { userInfo } = storeToRefs(useUserinfoStore())

const formData = reactive({
	userName: null,
	password: null
})
const rules = reactive({
	userName: [{ required: true, message: '请输入账号', trigger: 'blur' }],
	password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
})
const loading = ref(false)

const handleLogin = ({ validateResult, firstError }) => {
	if (validateResult === true) {
		loading.value = true
		const { userName, password } = formData
		const params = { userName, password: CryptoJS.MD5(String(password)).toString() }
		AUTH_CENTER.getVerifyUser(params)
			.then(({ data }) => {
				console.log(oauth2)
				if (data.warning) {
					MessagePlugin({ type: 'warning', message: data.warning })
					return
				}
				const { user, accessToken } = data
				userInfo.value = user
				oauth2.setOauth({ access_token: accessToken })
				router.push({ name: 'Expert' })
			})
			.finally(() => {
				loading.value = false
			})
	} else {
		console.log('Errors: ', validateResult)
		MessagePlugin.warning(firstError)
	}
}
</script>

<style lang="less" scoped>
.login-wrapper {
	width: 100%;
	height: 100vh;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	align-items: center;
	position: relative;
	background-image: url('@/assets/image/login-logo/登录背景.png');
	background-size: 100% 100%;
	position: relative;
	.login-logo {
		position: absolute;
		top: 30px;
		left: 50px;
		display: flex;
		align-items: center;
		width: 160px;
	}
	.login-title {
		position: absolute;
		top: 15%;
		left: 50%;
		transform: translateX(-50%);
		margin-right: 14px;
		font-size: 40px;
		color: #fff;
		text-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
	}
	.login-tabs {
		width: 100%;
		.top {
			display: flex;
			align-items: center;
			.top-common {
				display: flex;
				align-items: center;
				color: #0078e9;
				font-size: 14px;
				font-weight: bold;
				border-radius: 10px 10px 0 0;
				height: 40px;
				cursor: pointer;
			}
			.top-right {
				padding: 15px 27px;
				background-color: #fff;
			}
		}
	}
	.login-main {
		width: 400px;
		padding: 30px;
		background-color: white;
		border-top: 1px solid #d3d3ed;
		border-radius: 0 0 5px 5px;
	}
}
</style>
