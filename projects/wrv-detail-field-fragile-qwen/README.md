# wrv-detail-field-fragile

## Question ID: l1-136

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

AI质检报告列表页面，点击某些任务的"查看详情"打开详情弹窗后，检查项目区域有时显示"暂无检查项目数据"（即使接口确实返回了检查项列表）。有时检查项能显示出来，但"问题描述"列只显示"检查项ID: 42"这样的内部编号而非实际的检查描述文字。另外打开浏览器开发者工具可以看到 Vue 编译器相关的警告信息。
