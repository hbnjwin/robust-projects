# wrv-ws-event-mismatch

## Question ID: l1-125
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

任务进度监控组件（改进版）已成功连接WebSocket服务器，但任务进度更新和连接状态变化都无法正确反映在界面上——进度条不动、连接状态始终显示"未连接"。排查 src/components/task-progress/index-fixed.vue 第279行注册了wsManager.on('message', handleWebSocketMessage)监听消息事件，第280行注册了wsManager.on('statusChange', handleConnectionStatusChange)监听状态变化。但查看 src/utils/websocket-manager.js 的事件发射机制发现：WebSocketManager在handleMessage方法中根据消息类型分别发射'taskProgress'、'taskCompleted'、'taskFailed'等具体事件，只有未识别的消息类型才发射'message'事件（default分支）。因此正常的任务进度消息永远不会触发'message'事件处理器。同样，WebSocketManager发射的状态事件名是'connected'（第63行）、'disconnected'（第81行）、'error'（第91行），而非'statusChange'。组件监听的事件名与生产者发射的事件名完全不匹配，导致回调函数成为无法触发的死代码。需要修改事件名匹配实际的发射名称。
