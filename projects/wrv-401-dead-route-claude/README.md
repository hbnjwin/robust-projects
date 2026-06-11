# wrv-401-dead-route

## Question ID: l1-103

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

登录过期后 API 返回 401，页面弹了错误提示但始终停留在当前页无法跳转到登录页。排查 app-request.js 的响应拦截器发现，401 处理逻辑调用 router.push({ name: 'Auth.Send' })，但 Auth.Send 路由定义在 router/modules/auth-center.js 中，这个模块虽然存在但从未在 router/index.js 中被 import 和注册到 routerModules 数组。router.push 因为找不到路由名产生 NavigationFailure，用户被困在当前页面反复收到 401 错误弹窗。需要将 auth-center.js 模块导入并注册到路由中，或者将 401 跳转改为已注册的 Login 路由。