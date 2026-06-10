# wrv-ws-auth-bypass

## Question ID: l1-080

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

WebSocket 连接建立时没有做身份验证。HandshakeInterceptor 只校验了 Origin 头，没有在握手阶段验证 JWT token。未登录用户也能建立 WebSocket 连接，接收到所有审查任务的实时进度推送，存在信息泄露风险。而且 WebSocket 的 session 管理容器用的是普通 HashMap，多用户并发连接断开时有 ConcurrentModificationException 的风险。
