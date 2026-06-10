# wrv-ws-heartbeat-dup

## Question ID: l1-061

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

AI报告审查页面，用户打开一个审查任务后长时间不操作，进度条会同时显示两个不同的进度值来回跳动。看了下 websocket-manager.js 的心跳逻辑，断线重连时没有清理旧的 heartbeat 定时器，导致同一个连接上挂了两个心跳互相干扰。而且 subscribe 方法在重连后会重复注册事件监听，同一条进度消息被回调了两次。帮我修一下 WebSocket 的重连和心跳管理逻辑。
