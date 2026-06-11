# wrv-home-route-dead

## Question ID: l1-116
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

应用的「主页」模块完全无法访问——包括创建评审计划、分配审核任务、资料上传、文档预审、报告预审、报告实审、评审意见生成、归档等8个功能页面。在地址栏输入任何主页相关路径都会跳转到404页面。排查发现 src/router/modules/home.js 文件定义了完整的路由配置（164行代码，包含8个子路由及其嵌套子路由），但 src/router/index.js 中只导入了LoginRoute、ExpertDatabaseRoute、AiReportReviewRoute和SystemRoute四个模块，HomeRoute从未被import和注册到routerModules数组中。整个home路由模块是存在但未激活的死代码。注意home.js使用了path:'/'作为根路径，而expert-database.js也使用了path:'/'，导入时需要处理路径冲突问题。需要在router/index.js中导入home模块并注册，同时解决根路径冲突。
