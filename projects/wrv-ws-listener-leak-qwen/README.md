# wrv-ws-listener-leak

## Question ID: l1-100

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

任务进度组件（task-progress/index.vue）反复挂载和卸载后，WebSocket 消息处理出现异常——同一条消息被处理多次，控制台报已销毁组件的 reactive 引用错误。排查发现两个问题：第一，onUnmounted 只调用了 wsManager.disconnect() 断开连接，但从未调用 wsManager.off() 移除事件监听器，导致每次组件卸载后监听器仍然留在 wsManager 的 listeners Map 中。第二，setupWebSocketListeners 中 connected、disconnected、error 三个事件用了匿名箭头函数注册，即使调用 off() 也无法移除（indexOf 匹配不到匿名函数引用）。需要将所有匿名监听器改为具名函数引用，并在 onUnmounted 中逐一 off 移除。