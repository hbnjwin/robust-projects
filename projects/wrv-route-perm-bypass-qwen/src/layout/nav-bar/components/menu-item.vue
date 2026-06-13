<template>
	<t-menu-item :value="menu.auth" v-if="!menu.children || menu.children.length === 1" :to="{ name: menu.auth }">
		<span>{{ menu.label }}</span>
	</t-menu-item>
	<t-submenu v-else :value="menu.auth">
		<template #title>
			<span>{{ menu.label }}</span>
		</template>
		<menu-item v-for="item in menu?.children" :menu="item" :key="item.auth" />
	</t-submenu>
</template>

<script setup>
defineProps({
	menu: {
		type: Object,
		default: () => ({})
	}
})
</script>
<style lang="less" scoped></style>
