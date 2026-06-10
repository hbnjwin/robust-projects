# wrv-upload-icon-xlsx

## Question ID: l1-098

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

专家库上传文件弹窗（expert-database/upload-dialog.vue）上传 .xlsx 文件后，文件列表里的图标显示为破图。检查发现 accept 属性允许上传 .xlsx 文件，但 fileTypeToImage 映射对象里只有 "xls" 没有 "xlsx" 的键。用 split(".").pop() 取扩展名后在映射里找不到 "xlsx"，img 的 src 变成 undefined。同样的问题也存在于 expert-database/index.vue 的文件列表显示中。值得注意的是 common-function.js 的 fileTypeIcon 全局工具已经包含了 xlsx 的映射，但这两个地方没有复用，而是各自维护了一份不完整的映射。需要修复映射缺失并考虑复用全局工具函数。