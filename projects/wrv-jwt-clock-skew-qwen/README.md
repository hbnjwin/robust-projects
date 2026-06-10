# wrv-jwt-clock-skew

## Question ID: l1-078

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

JWT 认证在客户端和服务端时钟有几秒偏差时失效。JwtUtil 里的 token 过期校验用 new Date() 直接对比，没有预留 clock skew 窗口。用户反馈偶尔登录成功后第一个请求就返回 401，刷新页面又正常了。而且 token 里的 iat 如果比服务端当前时间晚几秒，验签直接抛 PrematureJwtException。帮我在校验逻辑里加上 30 秒的时钟偏差容忍。
