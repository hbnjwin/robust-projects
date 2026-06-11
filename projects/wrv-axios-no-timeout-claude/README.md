# wrv-axios-no-timeout

## Question ID: l1-115
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

当后端服务不可用或网络异常时，页面的API请求会无限等待，NProgress进度条一直在顶部滚动不停止，用户无法得到任何错误反馈，只能手动刷新页面。排查 src/api/app-request.js 第11行发现axios实例的timeout配置被设置为0。在axios中，timeout:0表示完全不设置超时限制，请求会无限期挂起直到TCP连接本身超时（通常是操作系统层面的很长时间）。正常的前端应用应该设置一个合理的超时时间（如15秒或30秒），超时后触发error interceptor显示错误信息并调用NProgress.done()恢复UI状态。需要将timeout设置为一个合理的毫秒值，如30000。
