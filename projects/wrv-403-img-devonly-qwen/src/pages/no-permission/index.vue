<template>
	<el-result>
		<template #icon>
			<img :src="errorImg" style="height: 70vh" />
		</template>
		<template #extra>
			<h1 class="m-b-20">很抱歉，您暂无权限访问</h1>
			<el-button type="text" @click="onLogin">返 回</el-button>
		</template>
	</el-result>
</template>

<script setup>
import oauth2 from '@/utils/oauth2'
import errorImg from '@/assets/image/error/403.svg'

const onLogin = () => {
	oauth2.remove()
	location.href = import.meta.env.VITE_AUTH_CENTER_BASE_URL + '/login?redirect_url=' + location.origin + '/#/auth/s'
}
</script>

<style lang="less" scoped></style>
