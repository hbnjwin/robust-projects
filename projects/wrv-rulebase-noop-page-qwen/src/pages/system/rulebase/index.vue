<template>
	<div class="common-wrapper">
		<div class="decoration">
			<div class="title">
				<div m-l-10px class="flex-start">
					<img m-r-10px style="width: 24px" src="@/assets/image/background/要素提取规则库icon.png" alt="" />要索提取规则库
				</div>
			</div>
			<div class="main">
				<div>
					<div class="flex-between" style="margin-bottom: 15px">
						<t-button theme="primary" type="submit" @click="handleCreate"><i class="iconfont icon-xinjianguize" text="16px" m-r-5px></i>新建规则</t-button>
						<div class="flex-start">
							<div>报告类型：</div>
							<t-select v-model="searchType" clearable style="width: 200px" m-r-15px placeholder="请选择" @change="handleSearch">
								<t-option v-for="item in reportTypeOptions" :key="item.value" :value="item.value" :label="item.label" />
							</t-select>
							<t-input v-model="searchKeyword" clearable placeholder="请输入内容" style="width: 260px" @enter="handleSearch" @clear="handleSearch">
								<template #suffixIcon>
									<i class="iconfont icon-sousuo" text="14px" @click="handleSearch"></i>
								</template>
							</t-input>
						</div>
					</div>
					<t-table
						row-key="index"
						hover
						:data="table.bodys"
						:columns="tableColumns"
						resizable
						lazy-load
						table-layout="fixed"
						max-height="calc(100vh - 350px)"
						:loading="table.loading"
					>
						<template #link="{ row }">
							<t-button variant="outline" theme="primary" size="small" @click="handleEdit(row)"
								><i class="iconfont icon-bianji" m-r-5px text="14px"></i>编辑</t-button
							>
							<t-button variant="outline" theme="primary" size="small" m-r-10px m-l-10px @click="handleCopy(row)"
								><i class="iconfont icon-fuzhi" m-r-5px text="14px"></i>复制</t-button
							>
							<t-button variant="outline" theme="danger" size="small" @click="handleDelete(row)"
								><i class="iconfont icon-shanchu" m-r-5px text="14px"></i>删除</t-button
							>
						</template>
					</t-table>
				</div>
				<div class="pagination-container">
					<table-pagination :pagination="table.pagination" @current-change="getTableList" @page-size-change="handlePageSizeChange" />
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import TablePagination from '@/components/table-pagination/index.vue'

const reportTypeOptions = [
	{ label: '审核报告', value: '审核报告' },
	{ label: '检测报告', value: '检测报告' },
	{ label: '评估报告', value: '评估报告' }
]

const searchType = ref('')
const searchKeyword = ref('')

const mockData = [
	{ projectNo: '电气审查规则', projectName: '审核报告', reviewStage: '已启用', deadline: '2024-01-15', status: '张三', version: 'v1.0', remark: '适用于电气专业图纸审查' },
	{ projectNo: '结构检测规则', projectName: '检测报告', reviewStage: '已启用', deadline: '2024-02-20', status: '李四', version: 'v2.1', remark: '用于结构安全性检测' },
	{ projectNo: '环境评估规则', projectName: '评估报告', reviewStage: '已停用', deadline: '2024-03-10', status: '王五', version: 'v1.3', remark: '环境影响评估专用' },
	{ projectNo: '消防审查规则', projectName: '审核报告', reviewStage: '已启用', deadline: '2024-04-05', status: '赵六', version: 'v3.0', remark: '消防合规性审查' },
	{ projectNo: '材料检测规则', projectName: '检测报告', reviewStage: '已启用', deadline: '2024-05-12', status: '张三', version: 'v1.5', remark: '建筑材料性能检测' },
	{ projectNo: '节能评估规则', projectName: '评估报告', reviewStage: '已启用', deadline: '2024-06-18', status: '李四', version: 'v2.0', remark: '建筑能效评估' },
	{ projectNo: '给排水审查规则', projectName: '审核报告', reviewStage: '已停用', deadline: '2024-07-22', status: '王五', version: 'v1.1', remark: '给排水系统设计审查' },
	{ projectNo: '地基检测规则', projectName: '检测报告', reviewStage: '已启用', deadline: '2024-08-30', status: '赵六', version: 'v2.3', remark: '地基承载力检测' }
]

const table = reactive({
	loading: false,
	bodys: [],
	search: {
		stationIds: [],
		manufactors: []
	},
	pagination: {
		page: 1,
		pageSize: 20,
		total: 0
	}
})
const tableColumns = ref([
	{ colKey: 'projectNo', title: '规则名称', width: 120, align: 'center', fixed: 'left', ellipsis: true },
	{ colKey: 'projectName', title: '规则类型', width: 120, align: 'center', fixed: 'left', ellipsis: true },
	{ colKey: 'reviewStage', title: '启用状态', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'deadline', title: '创建时间', width: 100, align: 'center', ellipsis: true },
	{ colKey: 'status', title: '创建人', width: 100, align: 'center', ellipsis: true },
	{ colKey: 'version', title: '版本号', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'remark', title: '备注', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'link', title: '操作', width: 130, align: 'center', fixed: 'right' }
])

const getTableList = (page) => {
	if (typeof page === 'number') table.pagination.page = page
	table.loading = true
	let filtered = [...mockData]
	if (searchType.value) {
		filtered = filtered.filter(item => item.projectName === searchType.value)
	}
	if (searchKeyword.value) {
		filtered = filtered.filter(item => item.projectNo.includes(searchKeyword.value))
	}
	table.pagination.total = filtered.length
	const start = (table.pagination.page - 1) * table.pagination.pageSize
	table.bodys = filtered.slice(start, start + table.pagination.pageSize)
	table.loading = false
}

const handleSearch = () => {
	table.pagination.page = 1
	getTableList()
}

const handleCreate = () => {
	MessagePlugin.info('新建规则')
}

const handleEdit = (row) => {
	MessagePlugin.info(`编辑规则：${row.projectNo}`)
}

const handleCopy = (row) => {
	const newRow = { ...row, projectNo: `${row.projectNo}(副本)` }
	mockData.push(newRow)
	getTableList()
	MessagePlugin.success('复制成功')
}

const handleDelete = (row) => {
	const confirmDialog = DialogPlugin.confirm({
		header: '确认删除',
		body: `确定要删除规则"${row.projectNo}"吗？`,
		onConfirm: () => {
			const index = mockData.findIndex(item => item.projectNo === row.projectNo)
			if (index !== -1) {
				mockData.splice(index, 1)
			}
			confirmDialog.destroy()
			getTableList()
			MessagePlugin.success('删除成功')
		},
		onClose: () => {
			confirmDialog.destroy()
		}
	})
}

const handlePageSizeChange = (newPageSize) => {
	table.pagination.pageSize = newPageSize
	table.pagination.page = 1
	getTableList()
}

onMounted(() => {
	getTableList()
})
</script>

<style lang="less" scoped>
.decoration {
	width: 100%;
	height: calc(100vh - 80px);
	display: flex;
	flex-direction: column;
	position: relative;
	.title {
		width: 100%;
		height: 80px;
		line-height: 50px;
		background-image: url('@/assets/image/background/要素提取规则库bg.png');
		background-size: cover;
		background-repeat: no-repeat;
		background-position: center;
		border-top-left-radius: 8px;
		border-top-right-radius: 8px;
	}
	.main {
		flex: 1;
		background-color: #fff;
		border-radius: 8px;
		margin-top: -30px;
		padding: 20px;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
	}
}
</style>
