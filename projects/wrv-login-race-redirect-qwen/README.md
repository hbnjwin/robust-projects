# wrv-login-race-redirect

## Question ID: l1-065

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

登录成功后，verifyUser 接口返回用户信息和 token，页面立刻并发发了3个初始化请求（部门树、功能菜单、用户详情），但偶尔有 1-2 个请求因为 cookie 还没写入就发出去了，返回 401 后被 axios 拦截器重定向到登录页。用户看到首页一闪而过然后又跳回登录。看了下 oauth2.js 的 setOauth 是同步写 cookie 但后续请求是在 then 链里同步发的，没有 await cookie 写入完成。
