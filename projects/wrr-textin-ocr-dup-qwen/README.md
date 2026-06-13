# wrr-textin-ocr-dup

## Question ID: l1-139

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

TextinService 类约1450行，包含8个以上结构高度相似的文档转换方法：convertPdfToMarkdownAsync、convertUrlToMarkdownAsync、convertPdfToMarkdown、convertUrlToMarkdown、uploadByBlueCloudAi、uploadByBlueCloudAiInternal、uploadByBlueCloudAiAsync、uploadBySysParasetOcr 及其重载版本和 uploadBySysParasetOcrAsync。每个方法都完整地重复了 HTTP 请求构建、OkHttp 调用、JSON响应解析、Markdown内容提取、文档实体保存、文件写入这套流程，只是在 OCR 提供商（Textin、BlueCloud、SysParaset）和同步/异步方式上有差异。上次修复响应体空指针问题时只改了其中4个方法，另外4个忘了改，导致特定提供商路径上出现未修复的崩溃。需要重构消除这些方法之间的重复。
