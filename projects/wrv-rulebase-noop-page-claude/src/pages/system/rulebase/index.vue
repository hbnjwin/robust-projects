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
							<t-select v-model="searchType" style="width: 200px" m-r-15px placeholder="请选择" clearable @change="handleSearch">
								<t-option v-for="item in reportTypeOptions" :key="item.value" :value="item.value" :label="item.label" />
							</t-select>
							<t-input v-model="searchKeyword" placeholder="请输入内容" style="width: 260px" clearable @enter="handleSearch" @clear="handleSearch">
								<template #suffixIcon>
									<i class="iconfont icon-sousuo" text="14px" style="cursor: pointer" @click="handleSearch"></i>
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

const mockData = [
	{ projectNo: '电气审查规则', projectName: '审核报告', reviewStage: '已启用', deadline: '2024-01-15', status: '张三', version: 'v1.0', remark: '适用于电气工程审查' },
	{ projectNo: '结构检测规则', projectName: '检测报告', reviewStage: '已启用', deadline: '2024-02-20', status: '李四', version: 'v2.1', remark: '更新了检测标准' },
	{ projectNo: '消防安全规则', projectName: '审核报告', reviewStage: '未启用', deadline: '2024-03-10', status: '王五', version: 'v1.2', remark: '待审批' },
	{ projectNo: '环境评估规则', projectName: '评估报告', reviewStage: '已启用', deadline: '2024-04-05', status: '赵六', version: 'v1.0', remark: '初始版本' },
	{ projectNo: '质量检验规则', projectName: '检测报告', reviewStage: '已启用', deadline: '2024-05-12', status: '张三', version: 'v3.0', remark: '重大版本更新' },
	{ projectNo: '安全生产规则', projectName: '审核报告', reviewStage: '未启用', deadline: '2024-06-01', status: '李四', version: 'v1.1', remark: '修复了规则匹配问题' },
	{ projectNo: '节能审查规则', projectName: '评估报告', reviewStage: '已启用', deadline: '2024-07-18', status: '王五', version: 'v2.0', remark: '增加了节能指标' },
	{ projectNo: '材料检测规则', projectName: '检测报告', reviewStage: '已启用', deadline: '2024-08-22', status: '赵六', version: 'v1.3', remark: '补充了新材料标准' }
]

const reportTypeOptions = [
	{ label: '审核报告', value: '审核报告' },
	{ label: '检测报告', value: '检测报告' },
	{ label: '评估报告', value: '评估报告' }
]

const searchType = ref('')
const searchKeyword = ref('')

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
	if (typeof page === 'number') {
		table.pagination.page = page
	}
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

const handlePageSizeChange = (newPageSize) => {
	table.pagination.pageSize = newPageSize
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
		confirmBtn: '确定',
		cancelBtn: '取消',
		onConfirm: () => {
			const index = mockData.findIndex(item => item === row)
			if (index > -1) {
				mockData.splice(index, 1)
			}
			getTableList()
			MessagePlugin.success('删除成功')
			confirmDialog.destroy()
		},
		onClose: () => {
			confirmDialog.destroy()
		}
	})
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
