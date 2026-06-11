<template>
	<div class="common-wrapper">
		<div class="decoration">
			<div class="title">
				<div m-l-10px class="flex-start">
					<img m-r-10px style="width: 24px" src="@/assets/image/background/报告专家库icon.png" alt="" />报告专家库
				</div>
			</div>
			<div class="main">
				<div>
					<div class="flex-between" style="margin-bottom: 15px">
						<t-button theme="primary" type="submit" @click="handleOpenUploadDialog"
							><i class="iconfont icon-baogaoshangchuan" text="16px" m-r-5px></i>报告上传</t-button
						>
						<div class="flex-start">
							<div>报告类型：</div>
							<t-select
								v-model="table.search.docType"
								style="width: 200px"
								m-r-15px
								placeholder="请选择"
								clearable
								@change="getTableList"
							>
								<t-option v-for="item in docTypeOptions" :key="item.value" :value="item.value" :label="item.label"></t-option>
							</t-select>
							<t-input placeholder="请输入内容" style="width: 260px" @change="getTableList" clearable v-model="table.search.keyWord">
								<template #suffixIcon>
									<i class="iconfont icon-sousuo" text="14px"></i>
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
						<template #processingStatus="{ row }">
							<t-tag v-if="row.processingStatus === 'UPLOADED'" theme="default" variant="light">已上传</t-tag>
							<t-tag v-else-if="row.processingStatus === 'OCR_PROCESSING'" theme="primary" variant="light">处理中</t-tag>
							<t-tag v-else-if="row.processingStatus === 'OCR_COMPLETED'" theme="success" variant="light">已完成</t-tag>
							<t-tag v-else-if="row.processingStatus === 'OCR_FAILED'" theme="danger" variant="light">失败</t-tag>
							<t-tag v-else-if="row.processingStatus === 'ARCHIVED'" theme="default" variant="light">已归档</t-tag>
						</template>
						<template #fileName="{ row }">
							<img :src="fileTypeToImage[row.fileType]" style="width: 16px" alt="" />
							{{ row.fileName }}
						</template>
						<template #docType="{ row }">
							<span v-if="row.docType === 0">已审核</span>
							<span v-else-if="row.docType === 1">待审核</span>
							<span v-else-if="row.docType === 2">可研报告</span>
						</template>
						<template #link="{ row }">
							<t-button variant="outline" theme="primary" size="small" @click="handleView(row)">查看</t-button>
							<t-button variant="outline" theme="primary" size="small" m-l-10px>编辑</t-button>
							<t-button variant="outline" theme="primary" size="small" m-l-10px>重新解析</t-button>
							<t-dropdown :options="dropdownOptions" @click="(data) => clickHandler(data, row)">
								<t-button theme="default" variant="outline" shape="square" size="small" m-l-10px>
									<t-icon name="ellipsis" size="16" />
								</t-button>
							</t-dropdown>
						</template>
					</t-table>
				</div>
				<div class="pagination-container">
					<table-pagination :pagination="table.pagination" @current-change="getTableList" @page-size-change="handlePageSizeChange" />
				</div>
			</div>
		</div>
		<upload-dialog ref="uploadDialogRef" @success="getTableList" />
	</div>
</template>

<script setup>
import { DialogPlugin, MessagePlugin } from 'tdesign-vue-next'
import router from '@/router'
import { EXPERT_DATABASE } from '@/api'
import UploadDialog from './components/upload-dialog.vue'
import TablePagination from '@/components/table-pagination/index.vue'
import doc from '@/assets/image/data-upload/doc.png'
import jpg from '@/assets/image/data-upload/jpg.png'
import docx from '@/assets/image/data-upload/docx.png'
import pdf from '@/assets/image/data-upload/pdf.png'
import png from '@/assets/image/data-upload/png.png'
import xls from '@/assets/image/data-upload/xls.png'

const fileTypeToImage = {
	DOC: doc,
	JPG: jpg,
	DOCX: docx,
	PDF: pdf,
	PNG: png,
	XLS: xls
}

const table = reactive({
	loading: false,
	bodys: [],
	search: {
		docType: null,
		where: 'fileName, originalFileName, docType, processingStatus, createdAt, link',
		keyWord: null
	},
	pagination: {
		page: 1,
		pageSize: 20,
		total: 0
	}
})
const tableColumns = ref([
	{ colKey: 'fileName', title: '文档名称', width: 200, align: 'center', fixed: 'left', ellipsis: true },
	{ colKey: 'originalFileName', title: '项目名称', width: 200, align: 'center', fixed: 'left', ellipsis: true },
	{ colKey: 'docType', title: '报告类型', width: 80, align: 'center', ellipsis: true },
	{ colKey: 'processingStatus', title: '解析状态', width: 100, align: 'center', ellipsis: true },
	{ colKey: 'createdAt', title: '上传时间', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'link', title: '操作', width: 110, align: 'center', fixed: 'right' }
])
const dropdownOptions = ref([{ content: '删除', value: 1 }])
const docTypeOptions = ref([
	{ label: '已审核', value: 0 },
	{ label: '待审核', value: 1 },
	{ label: '可研报告', value: 2 }
])

onMounted(() => {
	getTableList()
})

const getTableList = () => {
	table.loading = true
	let params = { ...table.pagination, docType: table.search.docType }
	if (table.search.keyWord) {
		params = { ...table.pagination, docType: table.search.docType, where: table.search.where, keyWord: table.search.keyWord }
	}
	EXPERT_DATABASE.getDocumentsList(params)
		.then(({ data }) => {
			const { list, total } = data.data
			table.bodys = list
			table.pagination.total = total
		})
		.finally(() => {
			table.loading = false
		})
}

const uploadDialogRef = ref(null)
const handleOpenUploadDialog = () => {
	uploadDialogRef.value.show()
}

const handlePageSizeChange = (newPageSize) => {
	table.pagination.pageSize = newPageSize
	table.pagination.page = 1
	getTableList()
}
const clickHandler = (data, row) => {
	if (data.value === 1) {
		const confirmDialog = DialogPlugin.confirm({
			header: '确认删除',
			body: `确定要删除文档「${row.fileName}」吗？`,
			confirmBtn: '确定',
			cancelBtn: '取消',
			onConfirm: () => {
				confirmDialog.destroy()
				EXPERT_DATABASE.deleteDocument(row.id)
					.then(() => {
						MessagePlugin.success('删除成功')
						getTableList()
					})
					.catch(() => {
						MessagePlugin.error('删除失败')
					})
			},
			onClose: () => {
				confirmDialog.destroy()
			}
		})
	}
}
const handleView = (row) => {
	router.push({ name: 'ExpertDatabaseView' })
	// router.push({ name: 'ExpertDatabaseView', query: { id: row.id } })
}
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
		background-image: url('@/assets/image/background/报告专家库bg.png');
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
