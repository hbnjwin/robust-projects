# wrv-api-silent-fail

## Question ID: l1-108

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

专家库页面偶尔显示空白列表但没有任何错误提示，用户以为没有数据实际上是请求失败了。排查 expert-database/index.vue 的 getTableList 方法发现，API 调用的 promise 链只有 .then() 和 .finally()，没有 .catch() 处理。当后端返回500错误或网络超时时，.then() 中的 const { list, total } = data.data 对 undefined 进行解构会抛出 TypeError，成为一个 unhandled rejection。.finally() 正常执行把 loading 设为 false，用户看到空表格以为没数据。对比 ai-report-review/index.vue 的列表接口有完善的 .catch() 和错误提示，这里的处理明显遗漏。需要添加 catch 处理、错误提示和防御性解构。