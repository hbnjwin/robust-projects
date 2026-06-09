# wrr-token-refresh-race

## Question ID: l1-032

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

后台管理系统放着不动过一会儿，连续点几个页面，接口偶尔会报 401 然后部分请求丢了。看了下 axios 拦截器里有个 token 刷新的队列逻辑，感觉是并发请求同时触发刷新的时候有竞态问题，排队的请求偶尔没被正确 replay。帮我修一下。
