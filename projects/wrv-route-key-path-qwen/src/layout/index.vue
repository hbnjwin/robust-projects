<template>
	<div>
		<t-layout>
			<t-header height="60px" style="z-index: 1">
				<nav-bar />
			</t-header>
			<t-layout>
				<t-content>
					<scrollbar height="calc(100vh - 60px)">
						<router-view v-slot="{ Component, route }">
							<transition name="slide-right" mode="out-in">
								<div :key="route.fullPath">
									<component :is="Component" />
								</div>
							</transition>
						</router-view>
					</scrollbar>
				</t-content>
			</t-layout>
		</t-layout>
	</div>
</template>

<script setup>
import NavBar from './nav-bar/index.vue'
import Scrollbar from '@/components/scrollbar/index.vue'
</script>

<style lang="less" scoped></style>
