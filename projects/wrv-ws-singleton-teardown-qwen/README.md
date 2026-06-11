# wrv-ws-singleton-teardown

## Question ID: l1-092

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

AI报告审查页面（ai-report-review/index.vue）和任务进度组件（task-progress/index.vue）共用同一个 WebSocketManager 单例。问题是当用户从AI审查页面切走时，组件的 onUnmounted 里调用了 wsManager.disconnect()，直接把全局唯一的 WebSocket 连接关闭了，导致页面上其他还在使用 WebSocket 的组件（比如任务进度组件）也全部断连。需要改成引用计数或者只移除自己的监听器，而不是直接断开全局连接。