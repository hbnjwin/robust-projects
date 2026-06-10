export class WebSocketManager {
  constructor(url) {
    this.url = url
    this.ws = null
    this.heartbeatTimer = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.heartbeatInterval = 30000
    this.listeners = {}
  }

  connect() {
    this.ws = new WebSocket(this.url)
    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.startHeartbeat()
    }
    this.ws.onclose = () => {
      console.log('WebSocket closed')
      this.reconnect()
    }
    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'pong') return
      this.emit(data.type, data)
    }
    this.ws.onerror = (err) => {
      console.error('WebSocket error', err)
    }
  }

  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, this.heartbeatInterval)
  }

  reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      setTimeout(() => this.connect(), 3000 * this.reconnectAttempts)
    }
  }

  subscribe(event, callback) {
    if (!this.listeners[event]) this.listeners[event] = []
    this.listeners[event].push(callback)
  }

  emit(event, data) {
    const cbs = this.listeners[event] || []
    cbs.forEach(cb => cb(data))
  }

  close() {
    if (this.ws) this.ws.close()
  }
}
