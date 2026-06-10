# wrv-dead-route-crash

## Question ID: l1-074

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

路由配置里 home.js 定义了 8 个子路由（创建评审计划、分配审核任务、资料上传等），引用的组件文件路径（src/pages/home/*）实际不存在。虽然 home.js 目前没有在 router/index.js 里被 import，但 auth-center.js 同样引用了不存在的 send.vue 和 receive.vue 组件。这些文件如果被意外引入会导致编译报错。帮我清理掉这些死路由文件和对应的 import，同时确认 router/index.js 里只导入了实际存在的路由模块。
