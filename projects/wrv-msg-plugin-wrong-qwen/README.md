# wrv-msg-plugin-wrong

## Question ID: l1-119
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

登录时服务端返回warning字段（如账号即将过期、密码需要修改等提示），页面应该弹出警告提示但实际没有任何提示显示，控制台也可能有错误。排查 src/pages/login/index.vue 第73行发现 MessagePlugin({ type: 'warning', message: data.warning }) 的调用方式不正确。TDesign的MessagePlugin有两种合法调用方式：一是 MessagePlugin.warning(content) 使用类型方法；二是 MessagePlugin('warning', { content: '...' }) 传入类型字符串和选项对象，且文本内容的属性名是content而非message。当前代码直接将MessagePlugin作为函数调用并传入包含type和message的对象，不符合任何合法签名。对比同文件第86行 MessagePlugin.warning(firstError) 使用了正确的调用方式。需要将第73行改为 MessagePlugin.warning(data.warning) 或 MessagePlugin('warning', { content: data.warning })。
