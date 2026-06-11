# wrv-route-key-path

## Question ID: l1-126
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

在需要通过URL查询参数（query params）控制页面内容的场景中（如分页?page=2、筛选?status=active），修改查询参数后页面内容不刷新，仍然显示旧数据。排查 src/layout/index.vue 第12行发现router-view的wrapper div使用了:key="route.path"作为组件重渲染的依据。route.path只包含路径部分（如/expert-database），不包含查询字符串和hash。因此当从/expert-database?page=1导航到/expert-database?page=2时，route.path没有变化，Vue认为是同一个组件实例不需要重新创建，组件的onMounted等生命周期钩子不会重新执行，依赖query参数获取数据的逻辑不会重新触发。正确的做法是使用route.fullPath作为key（包含path+query+hash），或者在组件内使用watch监听route.query的变化来重新获取数据。
