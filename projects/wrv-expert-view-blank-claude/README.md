# wrv-expert-view-blank

## Question ID: l1-097

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

专家库列表页点击「查看」按钮进入详情页后，页面完全空白。排查发现两个问题：第一，index.vue 的 handleView 方法调用 router.push 时没有传入记录 ID——传 ID 的那行代码被注释掉了。第二，view.vue 本身没有 onMounted 钩子也没有任何数据请求逻辑，模板里的报告名称、规则版本等字段都是硬编码的 "xxxx" 占位符，表格的 bodys 数组始终为空。需要恢复路由传参，并在 view.vue 中添加根据 ID 获取详情数据的逻辑。