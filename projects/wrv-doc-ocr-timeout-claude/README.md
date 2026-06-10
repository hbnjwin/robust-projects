# wrv-doc-ocr-timeout

## Question ID: l1-076

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: claude

## Query

文档 OCR 处理调用 TextinService，超过 30 页的 PDF 处理经常超时，但超时后文档状态没有从 OCR_PROCESSING 回退到 OCR_FAILED，一直卡在处理中。后续创建审查任务时引用这个文档，CheckResultServiceImpl 拿不到 OCR 结果，审查意见全是空值但任务状态显示成功。需要加 OCR 处理的超时兜底（比如 10 分钟未完成自动标记失败），以及审查任务对文档 OCR 状态的前置检查。
