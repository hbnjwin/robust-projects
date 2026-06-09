# wrr-ws-session-leak

## Question ID: l1-050

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

在线课堂用 WebSocket 做实时互动，但运行几天后服务端内存持续增长。ClassroomSessionManager 里用 ConcurrentHashMap 存 session，学生关浏览器后 onClose 回调偶尔没触发，session 对象就一直留在内存里。帮我加上心跳超时清理机制。
