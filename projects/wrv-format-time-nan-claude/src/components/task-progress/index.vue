<template>
	<div class="task-progress-container">
		<!-- 连接状态指示器 -->
		<div class="connection-status">
			<div class="status-indicator"></div>
			<span :class="connectionStatusClass">{{ connectionStatusText }}</span>
		</div>

		<!-- 任务进度列表 -->
		<div v-if="activeTasks.length > 0" class="active-tasks">
			<div class="tasks-header">
				<h4>正在执行的任�?({{ activeTasks.length }})</h4>
				<t-button size="small" variant="text" @click="refreshTasks">
					<i class="iconfont icon-shuaxin"></i>
				</t-button>
			</div>

			<div class="tasks-list">
				<div class="task-item" v-for="task in activeTasks" :key="task.taskId" :class="{ 'task-selected': selectedTaskId === task.taskId }">
					<div class="task-header">
						<div class="task-info">
							<span class="task-id">任务ID: {{ task.taskId }}</span>
							<span class="task-title">{{ task.taskTitle || task.taskId }}</span>
							<t-tag
								:theme="getStatusTheme(task.taskStatus)"
								variant="light"
								size="small"
							>
								{{ getStatusText(task.taskStatus) }}
							</t-tag>
						</div>
						<div class="task-actions">
							<t-button
								size="small"
								variant="text"
								@click="subscribeTask(task.taskId)"
								:disabled="selectedTaskId === task.taskId"
							>
								{{ selectedTaskId === task.taskId ? '已订�? : '订阅' }}
							</t-button>
							<t-button
								size="small"
								variant="text"
								theme="danger"
								@click="unsubscribeTask(task.taskId)"
								:disabled="selectedTaskId !== task.taskId"
							>
								取消订阅
							</t-button>
						</div>
					</div>

					<!-- 任务进度�?-->
					<div v-if="task.progress !== undefined" class="task-progress">
						<div class="progress-info">
							<span>进度: {{ task.progress }}%</span>
							<span v-if="task.currentItem">当前�? {{ task.currentItem }}</span>
						</div>
						<div class="progress-bar">
							<div class="progress-fill" :style="{ width: task.progress + '%' }"></div>
						</div>
					</div>

					<!-- 任务详细信息 -->
					<div v-if="selectedTaskId === task.taskId && task.details" class="task-details">
						<div class="detail-item" v-for="(value, key) in task.details" :key="key">
							<span class="detail-key">{{ key }}:</span>
							<span class="detail-value">{{ value }}</span>
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- 无活跃任务时的提�?-->
		<div v-else class="no-tasks">
			<i class="iconfont icon-wujieguo"></i>
			<p>暂无正在执行的任�?/p>
		</div>

		<!-- 消息日志 -->
		<div v-if="showLogs && messageLogs.length > 0" class="message-logs">
			<div class="logs-section">
				<h3>任务进度监控</h3>
				<t-button size="small" variant="text" @click="clearLogs">清空</t-button>
			</div>
			<div class="logs-container">
				<div class="log-item" v-for="(log, index) in messageLogs" :key="index" :class="log.type">
					<span class="log-time">{{ formatTime(log.time) }}</span>
					<span class="log-message">{{ log.message }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import wsManager from '@/utils/websocket-manager.js'

const props = defineProps({
	showLogs: {
		type: Boolean,
		default: false
	},
	autoConnect: {
		type: Boolean,
		default: true
	}
})

const emit = defineEmits(['taskProgress', 'taskCompleted', 'taskFailed', 'connectionChange'])

// 响应式数�?const connectionStatus = ref('CLOSED')
const activeTasks = ref([])
const selectedTaskId = ref(null)
const messageLogs = ref([])

// 计算属�?const connectionStatusClass = computed(() => {
	return {
		'status-connected': connectionStatus.value === 'OPEN',
		'status-connecting': connectionStatus.value === 'CONNECTING',
		'status-disconnected': connectionStatus.value === 'CLOSED'
	}
})

const connectionStatusText = computed(() => {
	switch (connectionStatus.value) {
		case 'OPEN':
			return '已连�?
		case 'CONNECTING':
			return '连接�?..'
		case 'CLOSED':
			return '未连�?
		default:
			return '未知状�?
	}
})

// 方法
const connectWebSocket = async () => {
	try {
		await wsManager.connect()
		connectionStatus.value = wsManager.getConnectionState()
	} catch (error) {
		console.error('连接WebSocket失败:', error)
		addLog('error', '连接WebSocket失败: ' + error.message)
	}
}

const disconnectWebSocket = () => {
	wsManager.disconnect()
	connectionStatus.value = wsManager.getConnectionState()
	selectedTaskId.value = null
}

const subscribeTask = (taskId) => {
	if (wsManager.isConnected()) {
		// 先取消之前的订阅
		if (selectedTaskId.value) {
			wsManager.unsubscribeTaskProgress()
		}

		// 订阅新任�?		wsManager.subscribeTaskProgress(taskId)
		selectedTaskId.value = taskId
		addLog('info', `已订阅任�? ${taskId}`)
	} else {
		ElMessage.warning('WebSocket未连接，请先连接')
	}
}

const unsubscribeTask = () => {
	if (wsManager.isConnected()) {
		wsManager.unsubscribeTaskProgress()
		selectedTaskId.value = null
		addLog('info', '已取消任务订�?)
	}
}

const refreshTasks = async () => {
	// 这里可以调用API获取活跃任务列表
	// 暂时使用模拟数据
	console.log('刷新任务列表')
}

const getStatusTheme = (status) => {
	switch (status) {
		case 'completed':
			return 'success'
		case 'failed':
			return 'danger'
		case 'processing':
		case 'started':
			return 'primary'
		case 'queued':
			return 'warning'
		default:
			return 'default'
	}
}

const getStatusText = (status) => {
	switch (status) {
		case 'completed':
			return '已完�?
		case 'failed':
			return '失败'
		case 'processing':
		case 'started':
			return '处理�?
		case 'queued':
			return '排队�?
		default:
			return '未知'
	}
}

const formatTime = (timeStr) => {
	if (!timeStr) return ''
	try {
		const date = new Date(timeStr)
		return date.toLocaleTimeString()
	} catch (error) {
		return timeStr
	}
}

const addLog = (type, message) => {
	const log = {
		type,
		message,
		time: new Date()
	}
	messageLogs.value.unshift(log)

	// 限制日志数量
	if (messageLogs.value.length > 100) {
		messageLogs.value = messageLogs.value.slice(0, 100)
	}
}

const clearLogs = () => {
	messageLogs.value = []
}

const updateTaskProgress = (progressData) => {
	const taskIndex = activeTasks.value.findIndex(task => task.taskId === progressData.taskId)

	if (taskIndex >= 0) {
		// 更新现有任务
		activeTasks.value[taskIndex] = { ...activeTasks.value[taskIndex], ...progressData }
	} else {
		// 添加新任�?		activeTasks.value.push(progressData)
	}

	emit('taskProgress', progressData)
}

const handleTaskCompleted = (data) => {
	updateTaskProgress({ ...data, taskStatus: 'completed' })
	addLog('success', `任务完成: ${data.taskId}`)
	emit('taskCompleted', data)
}

const handleTaskFailed = (data) => {
	updateTaskProgress({ ...data, taskStatus: 'failed' })
	addLog('error', `任务失败: ${data.taskId} - ${data.errorMessage}`)
	emit('taskFailed', data)
}

const handleTaskStarted = (data) => {
	updateTaskProgress({ ...data, taskStatus: 'started' })
	addLog('info', `任务开�? ${data.taskId}`)
}

const handleTaskItemCompleted = (data) => {
	addLog('info', `任务项完�? ${data.taskId} - ${data.itemName}`)
}

// WebSocket事件处理
const setupWebSocketListeners = () => {
	wsManager.on('connected', () => {
		connectionStatus.value = 'OPEN'
		addLog('success', 'WebSocket连接成功')
		emit('connectionChange', 'connected')
	})

	wsManager.on('disconnected', (data) => {
		connectionStatus.value = 'CLOSED'
		addLog('warning', `WebSocket连接断开: ${data.reason}`)
		emit('connectionChange', 'disconnected')
	})

	wsManager.on('error', (error) => {
		addLog('error', 'WebSocket错误: ' + error.message)
	})

	wsManager.on('taskProgress', updateTaskProgress)
	wsManager.on('taskCompleted', handleTaskCompleted)
	wsManager.on('taskFailed', handleTaskFailed)
	wsManager.on('taskStarted', handleTaskStarted)
	wsManager.on('taskItemCompleted', handleTaskItemCompleted)
}

// 生命周期
onMounted(() => {
	setupWebSocketListeners()

	if (props.autoConnect) {
		connectWebSocket()
	}
})

onUnmounted(() => {
	disconnectWebSocket()
})

// 暴露方法给父组件
defineExpose({
	connect: connectWebSocket,
	disconnect: disconnectWebSocket,
	subscribeTask,
	unsubscribeTask,
	isConnected: () => wsManager.isConnected(),
	getConnectionState: () => wsManager.getConnectionState()
})
</script>

<style lang="less" scoped>
.task-progress-container {
	background: #fff;
	border-radius: 8px;
	padding: 16px;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.connection-status {
	display: flex;
	align-items: center;
	margin-bottom: 16px;
	padding: 8px 12px;
	border-radius: 4px;
	font-size: 14px;

	.status-indicator {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		margin-right: 8px;
	}

	&.status-connected {
		background-color: #f6ffed;
		border: 1px solid #b7eb8f;
		color: #52c41a;

		.status-indicator {
			background-color: #52c41a;
		}
	}

	&.status-connecting {
		background-color: #fff7e6;
		border: 1px solid #ffd591;
		color: #fa8c16;

		.status-indicator {
			background-color: #fa8c16;
			animation: pulse 1.5s infinite;
		}
	}

	&.status-disconnected {
		background-color: #fff2f0;
		border: 1px solid #ffccc7;
		color: #ff4d4f;

		.status-indicator {
			background-color: #ff4d4f;
		}
	}
}

@keyframes pulse {
	0%, 100% { opacity: 1; }
	50% { opacity: 0.5; }
}

.active-tasks {
	.tasks-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;

		h4 {
			margin: 0;
			font-size: 16px;
			color: #333;
		}
	}
}

.tasks-list {
	max-height: 400px;
	overflow-y: auto;
}

.task-item {
	border: 1px solid #e8e8e8;
	border-radius: 6px;
	padding: 12px;
	margin-bottom: 8px;
	transition: all 0.3s;

	&:hover {
		border-color: #1890ff;
		box-shadow: 0 2px 4px rgba(24, 144, 255, 0.1);
	}

	&.task-selected {
		border-color: #1890ff;
		background-color: #f0f8ff;
	}
}

.task-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 8px;
}

.task-info {
	display: flex;
	align-items: center;
	gap: 8px;

	.task-title {
		font-weight: 500;
		color: #333;
	}
}

.task-progress {
	margin-bottom: 8px;

	.progress-info {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 4px;
		font-size: 12px;
		color: #666;

		.current-item {
			color: #1890ff;
		}
	}

	.progress-bar {
		height: 6px;
		background-color: #f0f0f0;
		border-radius: 3px;
		overflow: hidden;

		.progress-fill {
			height: 100%;
			background-color: #1890ff;
			transition: width 0.3s ease;
		}
	}
}

.task-error {
	display: flex;
	align-items: center;
	gap: 4px;
	color: #ff4d4f;
	font-size: 12px;
	margin-bottom: 8px;
}

.task-time {
	display: flex;
	justify-content: space-between;
	font-size: 11px;
	color: #999;
}

.no-tasks {
	text-align: center;
	padding: 40px 20px;
	color: #999;

	i {
		font-size: 48px;
		margin-bottom: 16px;
		display: block;
	}

	p {
		margin: 0;
		font-size: 14px;
	}
}

.message-logs {
	margin-top: 16px;
	border-top: 1px solid #e8e8e8;
	padding-top: 16px;

	.logs-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8px;

		h4 {
			margin: 0;
			font-size: 14px;
			color: #333;
		}
	}

	.logs-content {
		max-height: 200px;
		overflow-y: auto;
		background-color: #fafafa;
		border-radius: 4px;
		padding: 8px;
	}

	.log-item {
		display: flex;
		gap: 8px;
		margin-bottom: 4px;
		font-size: 12px;

		.log-time {
			color: #999;
			min-width: 60px;
		}

		.log-message {
			flex: 1;
		}

		&.success .log-message {
			color: #52c41a;
		}

		&.error .log-message {
			color: #ff4d4f;
		}

		&.warning .log-message {
			color: #fa8c16;
		}

		&.info .log-message {
			color: #1890ff;
		}
	}
}
</style>
