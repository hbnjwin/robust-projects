# wrr-portal-auth-redirect

## Question ID: l1-040

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

未登录用户在浏览器直接输入 /portal/courses/123 访问课程详情页，会被重定向到 /portal/index 首页而不是直接显示课程详情。门户页面本来就不需要登录。看了下 permission.ts 的白名单只写了 /portal 没有匹配子路由的带参数路径。
