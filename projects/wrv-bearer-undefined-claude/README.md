# wrv-bearer-undefined

## Question ID: l1-102

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

在未登录状态下访问页面，所有 API 请求返回 400 Bad Request 而不是预期的 401 Unauthorized。排查 app-request.js 的请求拦截器发现，Authorization 头始终拼接为 'Bearer ' + oauth2.getAccessToken()。当 cookie 不存在时，getOauth() 的 try-catch 返回空字符串 ''，然后 ''.access_token 是 undefined，最终请求头变成了字面量 "Bearer undefined"。服务端收到一个格式上合法但值无效的 token，返回 400 而非 401，导致响应拦截器中的 401 处理逻辑（清除 token + 跳转登录）永远触发不到。需要在拦截器中判断 token 是否存在，为空时不发送 Authorization 头。