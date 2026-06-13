<template>
	<div class="common-wrapper">
		<div class="ai-report-review">
			<div class="decoration">
				<div class="title">
					<div m-l-10px class="flex-start">
						<img m-r-10px style="width: 24px" src="@/assets/image/background/AI报告审核icon.png" alt="" />AI报告审核
					</div>
				</div>
				<div class="main">
					<div>
						<div class="flex-between" style="margin-bottom: 10px">
							<t-button theme="primary" type="submit" @click="handleOpenUploadDialog">
								<i class="iconfont icon-baogaoshangchuan" style="font-size: 16px; margin-right: 5px;"></i>报告上传
							</t-button>
						</div>
						<div class="flex-start" style="margin-bottom: 10px">
							<div>任务状态：</div>
							<t-select
								v-model="table.search.status"
								style="width: 200px"
								m-r-15px
								placeholder="请选择"
								clearable
								@change="getTableList"
							>
								<t-option v-for="item in statusOptions" :key="item.value" :value="item.value" :label="item.label"></t-option>
							</t-select>
							<t-input placeholder="请输入任务标题" style="width: 260px" @change="getTableList" clearable v-model="table.search.keyWord">
								<template #suffixIcon>
									<i class="iconfont icon-sousuo" text="14px"></i>
								</template>
							</t-input>
						</div>
					</div>
					<div class="table-container" style="margin-top: 0;">
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
							stripe
							size="medium"
							bordered
						>
							<template #status="{ row }">
								<t-tag v-if="row.status === 'queued'" theme="default" variant="light">排队中</t-tag>
								<t-tag v-else-if="row.status === 'started'" theme="primary" variant="light">执行中</t-tag>
								<t-tag v-else-if="row.status === 'completed'" theme="success" variant="light">已完成</t-tag>
								<t-tag v-else-if="row.status === 'failed'" theme="danger" variant="light">失败</t-tag>
							</template>
							<template #title="{ row }">
								<span :title="row.description">{{ row.title }}</span>
							</template>
							<template #progress="{ row }">
								<div class="progress-container">
									<div class="progress-bar">
										<div class="progress-fill" :style="{ width: (row.progress || 0) + '%' }"></div>
									</div>
									<span class="progress-text">{{ (row.progress || 0).toFixed(1) }}%</span>
								</div>
							</template>
							<template #actions="{ row }">
								<t-button
									variant="text"
									theme="success"
									@click="handleExecuteTask(row)"
									size="small"
									:disabled="row.status === 'started'"
								>
									{{ getActionText(row.status) }}
								</t-button>
								<t-button
									variant="text"
									theme="primary"
									@click="handleViewTask(row)"
									size="small"
									style="margin-left: 8px;"
								>
									查看详情
								</t-button>
							</template>
						</t-table>
					</div>
					<div class="pagination-container" style="margin-top: 15px;">
						<table-pagination :pagination="table.pagination" @current-change="getTableList" @page-size-change="handlePageSizeChange" />
					</div>
				</div>
			</div>
		</div>
		<upload-dialog ref="uploadDialogRef" @success="getTableList" />
		<task-detail-dialog ref="taskDetailDialogRef" />
	</div>
</template>

<script setup>
import AI_REPORT_REVIEW from '@/api/modules/ai-report-review.js'
import UploadDialog from './components/upload-dialog.vue'
import TaskDetailDialog from './components/task-detail-dialog.vue'
import { reactive, ref, onMounted, onUnmounted } from 'vue'
import TablePagination from '@/components/table-pagination/index.vue'
import wsManager from '@/utils/websocket-manager.js'

const table = reactive({
	loading: false,
	bodys: [],
	search: {
		status: null,
		keyWord: null
	},
	pagination: {
		page: 1,
		pageSize: 20,
		total: 0
	}
})
const tableColumns = ref([
	{ colKey: 'title', title: '任务标题', width: 200, align: 'left', ellipsis: true },
	{ colKey: 'status', title: '任务状态', width: 100, align: 'center' },
	{ colKey: 'progress', title: '进度', width: 120, align: 'center' },
	{ colKey: 'createdAt', title: '创建时间', width: 160, align: 'center' },
	{ colKey: 'startedAt', title: '开始时间', width: 160, align: 'center' },
	{ colKey: 'completedAt', title: '完成时间', width: 160, align: 'center' },
	{ colKey: 'actions', title: '操作', width: 180, align: 'center' }
])
const statusOptions = ref([
	{ label: '排队中', value: 'queued' },
	{ label: '执行中', value: 'started' },
	{ label: '已完成', value: 'completed' },
	{ label: '失败', value: 'failed' }
])

onMounted(() => {
	getTableList()
	initWebSocket()
})

onUnmounted(() => {
	cleanupWebSocket()
})

const getTableList = () => {
	table.loading = true
	let params = { ...table.pagination, status: table.search.status }
	if (table.search.keyWord) {
		params = { ...params, keyWord: table.search.keyWord }
	}
	AI_REPORT_REVIEW.getTasksList(params)
		.then(({ data }) => {
			const pageInfo = data.data
			table.bodys = pageInfo.list || []
			table.pagination.total = pageInfo.total || 0
		})
		.catch(error => {
			console.error('获取任务列表失败:', error)
		})
		.finally(() => {
			table.loading = false
		})
}

const uploadDialogRef = ref(null)
const taskDetailDialogRef = ref(null)
const handleOpenUploadDialog = () => {
	uploadDialogRef.value.show()
}

const handlePageSizeChange = (newPageSize) => {
	table.pagination.pageSize = newPageSize
	table.pagination.page = 1
	getTableList()
}


// WebSocket相关方法
const initWebSocket = async () => {
	try {
		// 连接WebSocket
		await wsManager.connect()
		console.log('WebSocket连接成功')

		// 添加任务进度监听事件
		wsManager.on('taskStarted', handleTaskStarted)
		wsManager.on('taskProgress', handleTaskProgress)
		wsManager.on('taskCompleted', handleTaskCompleted)
		wsManager.on('taskFailed', handleTaskFailed)
		wsManager.on('connected', () => {
			console.log('WebSocket已连接')
		})
		wsManager.on('disconnected', () => {
			console.log('WebSocket已断开')
		})
	} catch (error) {
		console.error('WebSocket连接失败:', error)
	}
}

const cleanupWebSocket = () => {
	// 移除事件监听
	wsManager.off('taskStarted', handleTaskStarted)
	wsManager.off('taskProgress', handleTaskProgress)
	wsManager.off('taskCompleted', handleTaskCompleted)
	wsManager.off('taskFailed', handleTaskFailed)

	// 断开连接
	wsManager.disconnect()
	console.log('WebSocket监听已清理')
}

// WebSocket事件处理函数
const handleTaskStarted = (data) => {
	console.log('任务开始:', data)
	updateTaskInList(data.taskId, {
		status: 'started',
		progress: 0,
		statusMessage: '任务已开始执行'
	})
}

const handleTaskProgress = (data) => {
	console.log('任务进度更新:', data)
	updateTaskInList(data.taskId, {
		status: data.taskStatus,
		progress: data.progressPercentage || 0,
		statusMessage: data.statusMessage,
		currentItemName: data.currentItemName
	})
}

const handleTaskCompleted = (data) => {
	console.log('任务完成:', data)
	updateTaskInList(data.taskId, {
		status: 'completed',
		progress: 100,
		statusMessage: '任务执行完成'
	})
	// 任务完成后刷新列表获取最新数据
	setTimeout(() => {
		getTableList()
	}, 1000)
}

const handleTaskFailed = (data) => {
	console.log('任务失败:', data)
	updateTaskInList(data.taskId, {
		status: 'failed',
		progress: data.progressPercentage || 0,
		statusMessage: data.statusMessage || '任务执行失败',
		errorMessage: data.errorMessage
	})
}

// 更新任务列表中的特定任务
const updateTaskInList = (taskId, updates) => {
	const taskIndex = table.bodys.findIndex(task => task.id === taskId)
	if (taskIndex !== -1) {
		// 使用Object.assign来更新任务对象，保持响应性
		Object.assign(table.bodys[taskIndex], updates)
		console.log(`任务 ${taskId} 状态已更新:`, updates)
	}
}

// 处理任务执行
const handleExecuteTask = (row) => {
	console.log('执行检查任务:', row)

	// 立即更新UI状态
	updateTaskInList(row.id, {
		status: 'started',
		progress: 0,
		statusMessage: '正在启动任务...'
	})

	// 执行增强检查任务
	AI_REPORT_REVIEW.executeEnhanceCheckTask(row.id)
		.then((response) => {
			console.log('任务执行请求成功:', response)
			// 订阅该任务的进度更新
			wsManager.subscribeTaskProgress(row.id)
		})
		.catch(error => {
			console.error('执行任务失败:', error)
			// 恢复任务状态
			updateTaskInList(row.id, {
				status: 'failed',
				progress: 0,
				statusMessage: '任务启动失败'
			})
		})
}

// 获取操作按钮文本
const getActionText = (status) => {
	switch (status) {
		case 'queued':
			return '执行任务'
		case 'started':
			return '执行中...'
		case 'completed':
			return '重新执行'
		case 'failed':
			return '重新执行'
		default:
			return '执行任务'
	}
}

// 查看任务详情
const handleViewTask = async (row) => {
	console.log('查看任务详情:', row)

	try {
		// 调用任务详情接口
		const { data } = await AI_REPORT_REVIEW.getTaskDetail(row.id)
		console.log('API响应数据:', data)

		// 显示详情弹窗
		if (data && data.data) {
			const taskData = data.data
			console.log('传递给对话框的数据:', taskData)
			taskDetailDialogRef.value.show(taskData)
		}

	} catch (error) {
		console.error('获取任务详情失败:', error)
	}
}

</script>

<style lang="less" scoped>
.decoration {
	width: 100%;
	min-height: calc(100vh - 80px);
	display: flex;
	flex-direction: column;
	position: relative;
	.title {
		width: 100%;
		height: 50px;
		line-height: 50px;
		background-image: url('@/assets/image/background/AI报告审核bg.png');
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
		margin-top: -15px;
		padding: 15px;
		display: flex;
		flex-direction: column;
		justify-content: flex-start;
	}
}

.task-progress-panel {
	margin-bottom: 10px;
}

.progress-container {
	display: flex;
	align-items: center;
	gap: 8px;
}

.progress-bar {
	width: 80px;
	height: 6px;
	background-color: #f0f0f0;
	border-radius: 3px;
	overflow: hidden;
}

.progress-fill {
	height: 100%;
	background-color: #1890ff;
	transition: width 0.3s ease;
}

.progress-text {
	font-size: 12px;
	color: #666;
	min-width: 40px;
}

.table-container {
	background: #fff;
	border-radius: 8px;
	overflow: hidden;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.table-container :deep(.t-table) {
	border-radius: 8px;
}

.table-container :deep(.t-table__header) {
	background: #f8f9fa;
	font-weight: 600;
}

.table-container :deep(.t-table__body) {
	font-size: 14px;
}

.table-container :deep(.t-table td) {
	padding: 12px 8px;
	vertical-align: middle;
}

.table-container :deep(.t-table th) {
	padding: 16px 8px;
	font-weight: 600;
	color: #333;
}
</style>
