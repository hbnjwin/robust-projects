<template>
	<div class="home-page">
		<nav-bar />
		<div class="home-content">
			<router-view v-slot="{ Component }">
				<transition name="fade" mode="out-in">
					<component :is="Component" />
				</transition>
			</router-view>
		</div>
	</div>
</template>

<script setup>
import NavBar from '@/components/nav-bar/index.vue'
</script>

<style scoped>
.home-page {
	min-height: 100vh;
}

.home-content {
	padding: 20px;
}

.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
</style>
