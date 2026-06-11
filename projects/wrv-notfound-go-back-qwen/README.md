# wrv-notfound-go-back

## Question ID: l1-110

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

404 页面底部的按钮文字是「返回首页」，但点击后并没有跳转到首页。排查 not-found/index.vue 发现 click 事件绑定的是 router.go(-1)（浏览器后退一步），而不是 router.push('/') 跳转首页。这导致三个问题：第一，如果用户直接输入了一个错误 URL 到达 404 页面，浏览器历史中没有上一页，go(-1) 完全无效，按钮点了没反应。第二，如果用户是从外部网站链接过来的，go(-1) 会离开当前应用跳到外部网站。第三，按钮文字承诺"返回首页"但实际行为是"返回上一页"，用户体验不一致。需要将 go(-1) 改为 push 到首页路由。