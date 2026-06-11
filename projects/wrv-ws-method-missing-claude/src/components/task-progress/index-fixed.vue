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
				<h4>正在执行的任务 ({{ activeTasks.length }})</h4>
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
								{{ selectedTaskId === task.taskId ? '已订阅' : '订阅' }}
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

					<!-- 任务进度条 -->
					<div v-if="task.progress !== undefined" class="task-progress">
						<div class="progress-info">
							<span>进度: {{ task.progress }}%</span>
							<span v-if="task.currentItem">当前项: {{ task.currentItem }}</span>
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

		<!-- 无活跃任务时的提示 -->
		<div v-else class="no-tasks">
			<i class="iconfont icon-wujieguo"></i>
			<p>暂无正在执行的任务</p>
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

const emit = defineEmits(['task-completed', 'task-failed', 'task-progress'])

// 响应式数据
const activeTasks = ref([])
const selectedTaskId = ref(null)
const messageLogs = ref([])
const connectionStatus = ref('disconnected')

// 计算属性
const connectionStatusClass = computed(() => {
	return {
		'status-connected': connectionStatus.value === 'connected',
		'status-connecting': connectionStatus.value === 'connecting',
		'status-disconnected': connectionStatus.value === 'disconnected'
	}
})

const connectionStatusText = computed(() => {
	const statusMap = {
		connected: '已连接',
		connecting: '连接中...',
		disconnected: '未连接'
	}
	return statusMap[connectionStatus.value] || '未知状态'
})

// 方法
const refreshTasks = async () => {
	try {
		// 这里可以调用API获取最新的任务列表
		console.log('刷新任务列表')
	} catch (error) {
		console.error('刷新任务失败:', error)
	}
}

const subscribeTask = (taskId) => {
	selectedTaskId.value = taskId
	wsManager.subscribeTaskProgress(taskId)
	addLog(`已订阅任务: ${taskId}`, 'info')
}

const unsubscribeTask = (taskId) => {
	if (selectedTaskId.value === taskId) {
		selectedTaskId.value = null
	}
	wsManager.unsubscribeTaskProgress()
	addLog(`已取消订阅任务: ${taskId}`, 'info')
}

const subscribeToTask = (taskId) => {
	subscribeTask(taskId)
}

const getStatusTheme = (status) => {
	const themeMap = {
		running: 'primary',
		completed: 'success',
		failed: 'danger',
		pending: 'default'
	}
	return themeMap[status] || 'default'
}

const getStatusText = (status) => {
	const textMap = {
		running: '执行中',
		completed: '已完成',
		failed: '失败',
		pending: '等待中'
	}
	return textMap[status] || status
}

const addLog = (message, type = 'info') => {
	const log = {
		message,
		type,
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

const formatTime = (time) => {
	return time.toLocaleTimeString()
}

const handleWebSocketMessage = (data) => {
	try {
		const message = typeof data === 'string' ? JSON.parse(data) : data
		
		if (message.type === 'task_progress') {
			handleTaskProgress(message)
		} else if (message.type === 'task_completed') {
			handleTaskCompleted(message)
		} else if (message.type === 'task_failed') {
			handleTaskFailed(message)
		}
	} catch (error) {
		console.error('处理WebSocket消息失败:', error)
	}
}

const handleTaskProgress = (message) => {
	const { taskId, progress, currentItem } = message
	
	// 更新任务进度
	const taskIndex = activeTasks.value.findIndex(task => task.taskId === taskId)
	if (taskIndex !== -1) {
		activeTasks.value[taskIndex].progress = progress
		activeTasks.value[taskIndex].currentItem = currentItem
	}
	
	addLog(`任务 ${taskId} 进度: ${progress}%`, 'info')
	emit('task-progress', message)
}

const handleTaskCompleted = (message) => {
	const { taskId } = message
	
	// 更新任务状态
	const taskIndex = activeTasks.value.findIndex(task => task.taskId === taskId)
	if (taskIndex !== -1) {
		activeTasks.value[taskIndex].taskStatus = 'completed'
		activeTasks.value[taskIndex].progress = 100
	}
	
	addLog(`任务 ${taskId} 已完成`, 'success')
	ElMessage.success(`任务 ${taskId} 执行完成`)
	emit('task-completed', message)
}

const handleTaskFailed = (message) => {
	const { taskId, error } = message
	
	// 更新任务状态
	const taskIndex = activeTasks.value.findIndex(task => task.taskId === taskId)
	if (taskIndex !== -1) {
		activeTasks.value[taskIndex].taskStatus = 'failed'
	}
	
	addLog(`任务 ${taskId} 执行失败: ${error}`, 'error')
	ElMessage.error(`任务 ${taskId} 执行失败`)
	emit('task-failed', message)
}

const handleConnectionStatusChange = (status) => {
	connectionStatus.value = status
	addLog(`连接状态变更: ${status}`, 'info')
}

// 生命周期
onMounted(() => {
	if (props.autoConnect) {
		wsManager.connect()
	}
	
	// 监听WebSocket事件
	wsManager.on('message', handleWebSocketMessage)
	wsManager.on('statusChange', handleConnectionStatusChange)
})

onUnmounted(() => {
	// 清理事件监听
	wsManager.off('message', handleWebSocketMessage)
	wsManager.off('statusChange', handleConnectionStatusChange)
})

// 暴露方法给父组件
defineExpose({
	subscribeToTask,
	refreshTasks,
	clearLogs
})
</script>

<style lang="less" scoped>
.task-progress-container {
	padding: 16px;
	background: #fff;
	border-radius: 8px;
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.connection-status {
	display: flex;
	align-items: center;
	margin-bottom: 16px;
	padding: 8px 12px;
	background: #f5f5f5;
	border-radius: 4px;
	
	.status-indicator {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		margin-right: 8px;
		background: #ccc;
	}
	
	.status-connected .status-indicator {
		background: #52c41a;
	}
	
	.status-connecting .status-indicator {
		background: #1890ff;
		animation: pulse 1.5s infinite;
	}
	
	.status-disconnected .status-indicator {
		background: #ff4d4f;
	}
}

.active-tasks {
	margin-bottom: 16px;
}

.tasks-header {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 12px;
	
	h4 {
		margin: 0;
		color: #333;
	}
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
		background: #f6ffed;
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
	gap: 12px;
	
	.task-id {
		font-weight: 500;
		color: #333;
	}
	
	.task-title {
		color: #666;
	}
}

.task-actions {
	display: flex;
	gap: 8px;
}

.task-progress {
	margin-top: 8px;
}

.progress-info {
	display: flex;
	justify-content: space-between;
	margin-bottom: 4px;
	font-size: 12px;
	color: #666;
}

.progress-bar {
	height: 6px;
	background: #f0f0f0;
	border-radius: 3px;
	overflow: hidden;
}

.progress-fill {
	height: 100%;
	background: #1890ff;
	transition: width 0.3s;
}

.task-details {
	margin-top: 8px;
	padding: 8px;
	background: #fafafa;
	border-radius: 4px;
}

.detail-item {
	display: flex;
	margin-bottom: 4px;
	
	&:last-child {
		margin-bottom: 0;
	}
}

.detail-key {
	font-weight: 500;
	margin-right: 8px;
	color: #333;
}

.detail-value {
	color: #666;
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
	border-top: 1px solid #e8e8e8;
	padding-top: 16px;
}

.logs-section {
	display: flex;
	justify-content: space-between;
	align-items: center;
	margin-bottom: 12px;
	
	h3 {
		margin: 0;
		font-size: 16px;
		color: #333;
	}
}

.logs-container {
	max-height: 200px;
	overflow-y: auto;
	border: 1px solid #e8e8e8;
	border-radius: 4px;
}

.log-item {
	padding: 8px 12px;
	border-bottom: 1px solid #f0f0f0;
	font-size: 12px;
	
	&:last-child {
		border-bottom: none;
	}
	
	&.info {
		background: #f6ffed;
		color: #52c41a;
	}
	
	&.success {
		background: #f6ffed;
		color: #52c41a;
	}
	
	&.error {
		background: #fff2f0;
		color: #ff4d4f;
	}
	
	&.warning {
		background: #fffbe6;
		color: #faad14;
	}
}

.log-time {
	margin-right: 8px;
	color: #999;
}

.log-message {
	color: inherit;
}

@keyframes pulse {
	0%, 100% {
		opacity: 1;
	}
	50% {
		opacity: 0.5;
	}
}
</style>
