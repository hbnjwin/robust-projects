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
						<t-button theme="primary" type="submit"><i class="iconfont icon-xinjianguize" text="16px" m-r-5px></i>新建规则</t-button>
						<div class="flex-start">
							<div>报告类型：</div>
							<t-select style="width: 200px" m-r-15px placeholder="请选择">
								<t-option key="orange" value="orange">Orange</t-option>
							</t-select>
							<t-input placeholder="请输入内容" style="width: 260px">
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
						<!-- <template #status="{ row }">
							<t-tag v-if="row.status === '进行中'" theme="primary" variant="light">{{ row.status }}</t-tag>
							<t-tag v-else-if="row.status === '已完成'" theme="success" variant="light">{{ row.status }}</t-tag>
							<t-tag v-else-if="row.status === '已延期'" theme="warning" variant="light">{{ row.status }}</t-tag>
							<t-tag v-else theme="default" variant="light">{{ row.status }}</t-tag>
						</template> -->
						<template #link="{ row }">
							<t-button variant="outline" theme="primary" size="small"
								><i class="iconfont icon-bianji" m-r-5px text="14px"></i>编辑</t-button
							>
							<t-button variant="outline" theme="primary" size="small" m-r-10px m-l-10px
								><i class="iconfont icon-fuzhi" m-r-5px text="14px"></i>复制</t-button
							>
							<t-button variant="outline" theme="danger" size="small"
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
// import router from '@/router'
import TablePagination from '@/components/table-pagination/index.vue'

const table = reactive({
	loading: false,
	bodys: [{}],
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
	{ colKey: 'creator', title: '版本号', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'creator', title: '备注', width: 120, align: 'center', ellipsis: true },
	{ colKey: 'link', title: '操作', width: 130, align: 'center', fixed: 'right' }
])

const getTableList = () => {}

const handlePageSizeChange = (newPageSize) => {
	table.pagination.pageSize = newPageSize
	table.pagination.page = 1
	getTableList()
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
