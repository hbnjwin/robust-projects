<template>
	<!-- 自定义列表-->
	<div class="custom-header m-l-10px" @click="open">
		<i class="iconfont icon-xitongshezhi icon cursor-pointer"></i>
	</div>
	<div class="custom-drawer">
		<el-drawer
			v-model="drawer.visible"
			direction="rtl"
			title="自定义显示列项"
			size="350px"
			:show-close="false"
			@opened="registerSort"
			@closed="destroySort"
		>
			<el-table ref="dragTable" :data="list" border row-key="label">
				<el-table-column label="显示" width="60px">
					<template #default="{ row }">
						<el-checkbox v-model="row.visible" />
					</template>
				</el-table-column>
				<el-table-column prop="label" label="列名"> </el-table-column>
				<el-table-column prop="sort" label="顺序" width="60px">
					<template #default>
						<i class="iconfont icon-shunxu cursor-move"></i>
					</template>
				</el-table-column>
			</el-table>
			<template #footer>
				<div class="mt-10px" style="text-align: center">
					<el-button class="plian-button mt-13px" style="width: 163px; border-color: #e8eef6" @click="handleReset"> 恢复默认</el-button
					><br />
					<el-button class="info-button mt-13px" style="width: 163px" @click="drawer.visible = false">取消</el-button><br />
					<el-button class="create-button mt-13px" style="width: 163px" @click="confirm">确定</el-button><br />
				</div>
			</template>
		</el-drawer>
	</div>
</template>
<script setup>
import Sortable from 'sortablejs'
import { useTableStore } from '@/store'

const props = defineProps({
	tableName: {
		type: String,
		required: true
	},
	defaultColumns: {
		type: Array,
		default: () => [],
		required: true
	}
})
let drawer = reactive({
	visible: false
})
const open = () => {
	drawer.visible = true
}
// 注册列表可排序
let list = ref([])
let sortableInstance = ref(null)
function registerSort() {
	const el = document.querySelector('.el-table__body-wrapper tbody')
	sortableInstance = Sortable.create(el, {
		ghostClass: 'sortable-ghost',
		setData: function (dataTransfer) {
			dataTransfer.setData('Text', '')
		},
		onEnd({ newIndex, oldIndex }) {
			const currRow = list.value.splice(oldIndex, 1)[0]
			list.value.splice(newIndex, 0, currRow)
		}
	})
}
let destroySort = function () {
	sortableInstance?.destroy()
}
// 获取vuex里保存的数据
const { tableStoreColumns, updateColumns } = useTableStore()
const columns = computed(() => {
	return tableStoreColumns[props.tableName]
})

// 初始化
onMounted(() => {
	handleInit()
})
function handleInit() {
	list.value = JSON.parse(JSON.stringify(columns.value || props.defaultColumns))
}
/** 处理重置为默认表头 */
function handleReset() {
	list.value = JSON.parse(JSON.stringify(props.defaultColumns))
}
// 确定
function confirm() {
	// 排序
	let saveList = list.value.map((item, index) => {
		item.order = index
		return item
	})
	updateColumns({ prop: props.tableName, value: saveList })
	drawer.visible = false
}
</script>

<style>
.sortable-ghost {
	color: #fff !important;
	background-color: rgba(0, 0, 0, 0.1) !important;
}
</style>

<style lang="less" scoped>
.custom-drawer {
	:deep(.el-drawer) {
		border-radius: 20px 0px 0px 0px;
	}
	:deep(.el-drawer__header) {
		height: 48px;
		line-height: 48px;
		text-align: center;
		background: var(--el-color-primary);
		color: #fff;
		border-radius: 20px 0px 0px 0px;
		padding: 0;
		margin: 0;
	}
}

.custom-header {
	box-sizing: border-box;
	display: flex;
	justify-content: center;
	align-items: center;
	width: 32px;
	height: 32px;
	background-color: #fff;
	border-radius: 2px 2px 2px 2px;
	opacity: 1;
	border: 1px solid #e5e6eb;
	cursor: pointer;
	&:hover {
		background-color: #dcecff;
		.icon {
			color: #165dff;
		}
	}
	.icon {
		font-size: 18px;
	}
}

.create-button {
	line-height: 1;
	color: #fff;
	background: var(--el-color-primary);
	border-radius: 4px;
	cursor: pointer;
	border: 1px solid var(--el-color-primary);
	&:hover {
		color: #fff;
		background: #409eff;
	}
	&:focus {
		color: #fff;
		background: var(--el-color-primary);
	}
}
.plian-button {
	color: var(--el-color-primary);
	&:hover {
		color: #ffffff;
	}
}
</style>
