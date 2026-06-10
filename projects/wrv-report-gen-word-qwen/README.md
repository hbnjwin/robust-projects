# wrv-report-gen-word

## Question ID: l1-084

## Task Type: feature

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

接入现有的 WordReportGenerator 模块，提供一个 API 接口让前端能一键生成审查报告 Word 文档。报告内容包括：项目基本信息（从 ProjectInfo 取）、检查结果摘要、每个检查项的详细审查意见。模板用 poi-tl 渲染，支持表格和段落。生成后的文件上传到文件服务返回下载链接。
