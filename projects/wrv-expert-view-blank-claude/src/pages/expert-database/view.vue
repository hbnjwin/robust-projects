<template>
	<div class="common-wrapper">
		<div class="flex-start m-b-5px">
			<t-button variant="text" theme="primary" size="medium" @click="$router.go(-1)">
				<i class="iconfont icon-fanhui" text="10px" m-r-5px></i>返回</t-button
			>
			<t-divider layout="vertical" />
			<t-breadcrumb m-l-10px>
				<t-breadcrumbItem>报告专家库</t-breadcrumbItem>
				<t-breadcrumbItem>提取结果确认</t-breadcrumbItem>
			</t-breadcrumb>
		</div>
		<div class="decoration">
			<div class="decoration-top flex-between">
				<div>
					<span>报告名称: xxxx</span>
					<span m-l-30px>使用规则版本: xxxx</span>
				</div>
				<div>
					<t-button variant="outline" theme="default" m-r-10px
						><i class="iconfont icon-zhongxintiqu" text="16px" m-r-5px></i>重新提取</t-button
					>
					<t-button theme="primary" type="submit"><i class="iconfont icon-tiquchenggong" text="16px" m-r-5px></i>确认通过</t-button>
				</div>
			</div>
			<div class="main">
				<div>
					<div class="flex-between" style="margin-bottom: 15px">
						<t-radio-group variant="default-filled" default-value="0">
							<t-radio-button value="0">全部</t-radio-button>
							<t-radio-button value="1">提取成功</t-radio-button>
							<t-radio-button value="2">提取失败</t-radio-button>
						</t-radio-group>
						<t-input placeholder="请输入内容" style="width: 260px">
							<template #suffixIcon>
								<i class="iconfont icon-sousuo" text="14px"></i>
							</template>
						</t-input>
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
						<template #link="{ row }">
							<t-button variant="outline" theme="primary" size="small">编辑</t-button>
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
import TablePagination from '@/components/table-pagination/index.vue'

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
	{ colKey: 'fileName', title: '序号', width: 120, align: 'center', fixed: 'left', ellipsis: true },
	{ colKey: 'originalFileName', title: '提取项目名', width: 120, align: 'center', fixed: 'left', ellipsis: true },
	{ colKey: 'fileType', title: '来源位置', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'processingStatus', title: '状态', width: 100, align: 'center', ellipsis: true },
	{ colKey: '', title: '匹配规则', width: 100, align: 'center', ellipsis: true },
	{ colKey: 'createdAt', title: '提取结果', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'link', title: '操作', width: 80, align: 'center', fixed: 'right' }
])
</script>

<style lang="less" scoped>
.decoration {
	width: 100%;
	height: calc(100vh - 120px);
	display: flex;
	flex-direction: column;
	position: relative;
	background-color: #fff;
	border-radius: 8px;
	.decoration-top {
		padding: 0 10px;
		height: 50px;
		border-bottom: 1px solid #ebebeb;
	}
	.main {
		flex: 1;
		background-color: #fff;
		border-radius: 8px;
		padding: 10px;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
	}
}
</style>
