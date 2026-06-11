<template>
	<t-pagination
		class="m-t-15px"
		v-model="currentPage"
		:total="props.pagination.total"
		:page-size="props.pagination.pageSize"
		:page-size-options="[20, 50, 100]"
		@current-change="handleCurrentChange"
		@page-size-change="handlePageSizeChange"
	/>
</template>

<script setup>
import { computed } from 'vue'

const emits = defineEmits(['update:pagination'])

const props = defineProps({
	pagination: {
		type: Object,
		default: () => ({})
	}
})

const currentPage = computed({
	get: () => props.pagination.page,
	set: () => {
		// 赋值由 t-pagination 的 current-change 事件驱动，此处无需操作
	}
})

const handleCurrentChange = (newPage) => {
	emits('update:pagination', { ...props.pagination, page: newPage })
}

const handlePageSizeChange = (newPageSize) => {
	emits('update:pagination', { ...props.pagination, pageSize: newPageSize, page: 1 })
}

defineExpose({ handleCurrentChange, handlePageSizeChange })
</script>

<style lang="less" scoped></style>
