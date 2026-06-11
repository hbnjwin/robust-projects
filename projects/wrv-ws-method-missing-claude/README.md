# wrv-ws-method-missing

## Question ID: l1-124
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

任务进度监控组件（改进版）的订阅和取消订阅按钮点击后报TypeError: wsManager.subscribeToTask is not a function。排查 src/components/task-progress/index-fixed.vue 第151行调用了wsManager.subscribeToTask(taskId)，第159行调用了wsManager.unsubscribeFromTask(taskId)。但查看 src/utils/websocket-manager.js 的WebSocketManager类定义，实际的方法名是subscribeTaskProgress(taskId)（第136行）和unsubscribeTaskProgress()（第147行）。方法名完全不匹配——subscribeToTask vs subscribeTaskProgress，unsubscribeFromTask vs unsubscribeTaskProgress。此外unsubscribeTaskProgress()不接受参数（它取消所有任务订阅），而代码传入了taskId参数。需要将两处方法调用修正为websocket-manager.js中实际定义的方法名。
