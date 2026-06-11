<template>
	<el-result>
		<template #icon>
			<img src="/src/assets/image/error/404.svg" style="height: 70vh" />
		</template>
		<template #extra>
			<h1 class="m-b-20">很抱歉，您所访问的页面不存在</h1>
			<el-button type="text" @click="router.go(-1)">返回首页</el-button>
		</template>
	</el-result>
</template>

<script setup>
const router = useRouter()
</script>

<style lang="less" scoped></style>
