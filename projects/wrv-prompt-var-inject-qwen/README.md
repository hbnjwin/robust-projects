# wrv-prompt-var-inject

## Question ID: l1-081

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

PromptTemplates 的提示词模板在渲染时用字符串拼接把文档内容直接插入 prompt，没有做转义或长度限制。如果文档内容里包含 LLM 注入攻击文本，会影响 AI 审查结果的准确性。同时模板里的变量占位符 ${documentContent} 如果在文档正文里也出现了，MVEL2 表达式引擎会循环替换导致 StackOverflowError。
