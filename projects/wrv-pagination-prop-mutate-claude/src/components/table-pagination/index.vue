<template>
	<t-pagination
		class="m-t-15px"
		v-model="props.pagination.page"
		:total="props.pagination.total"
		:page-size="props.pagination.pageSize"
		:page-size-options="[20, 50, 100]"
		@current-change="handleCurrentChange"
		@page-size-change="handlePageSizeChange"
	/>
</template>

<script setup>
const emits = defineEmits(['current-change', 'page-size-change'])

const props = defineProps({
	pagination: {
		type: Object,
		default: () => {}
	}
})

const handleCurrentChange = () => {
	emits('current-change')
}

const handlePageSizeChange = (newPageSize) => {
	emits('page-size-change', newPageSize)
}

defineExpose({ handleCurrentChange, handlePageSizeChange })
</script>

<style lang="less" scoped></style>
