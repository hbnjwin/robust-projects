# wrv-llm-call-unify

## Question ID: l1-090

## Task Type: refactor-maintenance

## App Domain: backend_service

## Language: java

## Model: claude

## Query

当前的 LLM 调用逻辑分散在 AiController、PromptExecutionService、CheckResultServiceImpl 等多个地方，每处都单独处理了 HTTP 请求构建、重试逻辑、错误处理和响应解析。Azure OpenAI 和 DeepSeek 用了完全不同的调用方式。帮我把所有 LLM 调用统一收拢到 DynamicLLMService，定义统一的请求/响应接口，不同 provider 用策略模式切换。
