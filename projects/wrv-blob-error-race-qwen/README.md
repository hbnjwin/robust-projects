# wrv-blob-error-race

## Question ID: l1-118
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

文件下载接口返回错误时，偶尔会出现错误提示延迟弹出，或者在.catch()中无法获取到错误信息（收到的是一个Blob对象而非JSON数据）。排查 src/api/app-request.js 第34-52行的响应拦截器发现，当blob类型响应的Content-Type包含json时（表示服务端返回了JSON格式的错误信息而非文件），代码使用FileReader异步读取blob内容并在onload回调中显示错误消息。但FileReader.readAsText()是异步操作，代码在启动读取后立即设置responseError=true并在第52行返回Promise.reject(res.data)。此时res.data仍然是原始的Blob对象（FileReader还没读完），调用者的catch处理器收到的是一个无法直接使用的Blob。另外ElMessage的错误提示在异步的onload回调中触发，时机不可控。需要将FileReader读取改为Promise包装（或使用Blob.text()），在读取完成后再reject解析后的JSON数据。
