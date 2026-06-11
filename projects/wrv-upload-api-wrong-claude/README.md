# wrv-upload-api-wrong

## Question ID: l1-099

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

AI报告审查的上传文件弹窗（ai-report-review/upload-dialog.vue）点击上传后报 TypeError: EXPERT_DATABASE.postDocumentsUploadFile is not a function。原因是这个组件导入了错误的 API 模块——import 的是 EXPERT_DATABASE 而不是 AI_REPORT_REVIEW。postDocumentsUploadFile 方法定义在 ai-report-review.js 模块中，而 expert-database.js 模块只有 getDocumentsList 一个方法。另外 ai-report-review.js 甚至没有在 api/index.js 中导出，需要补充导出。上传成功后的文件列表刷新也调用了错误模块的接口。