/**
 * WebSocket连接管理器
 * 用于管理任务进度实时通知
 */
class WebSocketManager {
	constructor() {
		this.ws = null
		this.reconnectTimer = null
		this.heartbeatTimer = null
		this.reconnectAttempts = 0
		this.maxReconnectAttempts = 5
		this.reconnectInterval = 3000
		this.heartbeatInterval = 30000
		this.listeners = new Map()
		this.isConnecting = false
		this.isManualClose = false

		// WebSocket服务器地址
		this.wsUrl = this.getWebSocketUrl()
	}

	/**
	 * 获取WebSocket服务器地址
	 */
	getWebSocketUrl() {
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'

		// 从环境变量读取WebSocket配置
		const host = import.meta.env.VITE_WEBSOCKET_HOST || window.location.hostname
		const port = import.meta.env.VITE_WEBSOCKET_PORT || '8020'
		const path = import.meta.env.VITE_WEBSOCKET_PATH || '/reportReview'

		return `${protocol}//${host}:${port}${path}`
	}

	/**
	 * 连接WebSocket
	 */
	connect() {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			console.log('WebSocket已连接')
			return Promise.resolve()
		}

		if (this.isConnecting) {
			console.log('WebSocket正在连接中...')
			return Promise.resolve()
		}

		return new Promise((resolve, reject) => {
			try {
				this.isConnecting = true
				this.isManualClose = false

				console.log('正在连接WebSocket:', this.wsUrl)
				this.ws = new WebSocket(this.wsUrl)

				this.ws.onopen = () => {
					console.log('WebSocket连接成功')
					this.isConnecting = false
					this.reconnectAttempts = 0
					this.startHeartbeat()
					this.emit('connected')
					resolve()
				}

				this.ws.onmessage = (event) => {
					try {
						const message = JSON.parse(event.data)
						console.log('收到WebSocket消息:', message)
						this.handleMessage(message)
					} catch (error) {
						console.error('解析WebSocket消息失败:', error, event.data)
					}
				}

				this.ws.onclose = (event) => {
					console.log('WebSocket连接关闭:', event.code, event.reason)
					this.isConnecting = false
					this.stopHeartbeat()
					this.emit('disconnected', { code: event.code, reason: event.reason })

					if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
						this.scheduleReconnect()
					}
				}

				this.ws.onerror = (error) => {
					console.error('WebSocket连接错误:', error)
					this.isConnecting = false
					this.emit('error', error)
					reject(error)
				}
			} catch (error) {
				this.isConnecting = false
				console.error('创建WebSocket连接失败:', error)
				reject(error)
			}
		})
	}

	/**
	 * 断开WebSocket连接
	 */
	disconnect() {
		this.isManualClose = true
		this.stopHeartbeat()
		this.clearReconnectTimer()

		if (this.ws) {
			this.ws.close()
			this.ws = null
		}

		console.log('WebSocket连接已断开')
	}

	/**
	 * 发送消息
	 */
	send(message) {
		if (this.ws && this.ws.readyState === WebSocket.OPEN) {
			const messageStr = typeof message === 'string' ? message : JSON.stringify(message)
			this.ws.send(messageStr)
			console.log('发送WebSocket消息:', message)
			return true
		} else {
			console.warn('WebSocket未连接，无法发送消息:', message)
			return false
		}
	}

	/**
	 * 订阅任务进度
	 */
	subscribeTaskProgress(taskId) {
		const message = {
			type: 'task_subscribe',
			taskId: taskId
		}
		return this.send(message)
	}

	/**
	 * 取消订阅任务进度
	 */
	unsubscribeTaskProgress() {
		const message = {
			type: 'task_unsubscribe'
		}
		return this.send(message)
	}

	/**
	 * 处理接收到的消息
	 */
	handleMessage(message) {
		const { type, data } = message

		switch (type) {
			case 'task_progress':
				this.emit('taskProgress', data)
				break
			case 'task_started':
				this.emit('taskStarted', data)
				break
			case 'task_completed':
				this.emit('taskCompleted', data)
				break
			case 'task_failed':
				this.emit('taskFailed', data)
				break
			case 'task_item_completed':
				this.emit('taskItemCompleted', data)
				break
			case 'pong':
				console.log('收到心跳响应')
				break
			default:
				console.log('未知消息类型:', type, data)
				this.emit('message', message)
		}
	}

	/**
	 * 开始心跳检测
	 */
	startHeartbeat() {
		this.stopHeartbeat()
		this.heartbeatTimer = setInterval(() => {
			if (this.ws && this.ws.readyState === WebSocket.OPEN) {
				this.send({ type: 'ping' })
			}
		}, this.heartbeatInterval)
	}

	/**
	 * 停止心跳检测
	 */
	stopHeartbeat() {
		if (this.heartbeatTimer) {
			clearInterval(this.heartbeatTimer)
			this.heartbeatTimer = null
		}
	}

	/**
	 * 安排重连
	 */
	scheduleReconnect() {
		this.clearReconnectTimer()
		this.reconnectAttempts++

		console.log(`准备重连WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)

		this.reconnectTimer = setTimeout(() => {
			this.connect().catch(error => {
				console.error('重连WebSocket失败:', error)
			})
		}, this.reconnectInterval)
	}

	/**
	 * 清除重连定时器
	 */
	clearReconnectTimer() {
		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer)
			this.reconnectTimer = null
		}
	}

	/**
	 * 添加事件监听器
	 */
	on(event, callback) {
		if (!this.listeners.has(event)) {
			this.listeners.set(event, [])
		}
		this.listeners.get(event).push(callback)
	}

	/**
	 * 移除事件监听器
	 */
	off(event, callback) {
		if (this.listeners.has(event)) {
			const callbacks = this.listeners.get(event)
			const index = callbacks.indexOf(callback)
			if (index > -1) {
				callbacks.splice(index, 1)
			}
		}
	}

	/**
	 * 触发事件
	 */
	emit(event, data) {
		if (this.listeners.has(event)) {
			this.listeners.get(event).forEach(callback => {
				try {
					callback(data)
				} catch (error) {
					console.error('事件回调执行失败:', event, error)
				}
			})
		}
	}

	/**
	 * 获取连接状态
	 */
	getConnectionState() {
		if (!this.ws) return 'CLOSED'

		switch (this.ws.readyState) {
			case WebSocket.CONNECTING:
				return 'CONNECTING'
			case WebSocket.OPEN:
				return 'OPEN'
			case WebSocket.CLOSING:
				return 'CLOSING'
			case WebSocket.CLOSED:
				return 'CLOSED'
			default:
				return 'UNKNOWN'
		}
	}

	/**
	 * 检查是否已连接
	 */
	isConnected() {
		return this.ws && this.ws.readyState === WebSocket.OPEN
	}
}

// 创建全局WebSocket管理器实例
const wsManager = new WebSocketManager()

export default wsManager
