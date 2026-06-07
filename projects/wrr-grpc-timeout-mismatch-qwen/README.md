# wrr-grpc-timeout-mismatch

## Question ID: l1-014

## Task Type: bug-fix

## App Domain: backend_service

## Language: go

## Model: qwen

## Query

Go 写的微服务，有个 gRPC 接口偶尔返回 context deadline exceeded，客户端超时了但服务端日志显示处理成功了。帮我查下这个不一致的问题。
