# wrv-dialog-form-stale

## Question ID: l1-134

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

在AI质检报告页面，点击"报告上传"打开上传弹窗，选择一个 PDF 文件并设置文档类型，然后点击取消关闭弹窗。再次点击"报告上传"重新打开弹窗时，之前选择的 PDF 文件仍然显示在"已传文件"区域，文档类型下拉框也保留着上次的选择。预期每次打开弹窗应该是一个干净的空表单。专家库的上传弹窗也有相似问题，并且打开后上传组件的文件状态显示异常。
