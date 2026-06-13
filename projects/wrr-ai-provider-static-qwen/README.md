# wrr-ai-provider-static

## Question ID: l1-143

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

系统的AI服务调用逻辑分散在 CommonFunc 类的多个独立静态方法中：CallOpenAiBySse 处理Azure OpenAI流式调用（含SSL配置和OkHttp客户端创建），callNewOpenAi 处理Azure新版本调用，callAi 和 callAiWithOkHttp 处理Linkyoyo Agent调用（含完整的嵌套JSON请求体构建），callDeepSeekAi 处理DeepSeek调用。每个方法都从头创建HTTP客户端、配置SSL信任管理器、构建请求体、解析响应。DynamicLLMService 试图统一这些调用，但它的 callLLM 方法内部仍然是一个 switch 语句分派到各自的私有方法，而且 buildLinkyoyoAgentRequest 方法（80行）与 CommonFunc.callAi 中的请求构建逻辑完全重复。SSL信任管理器的信任所有证书配置在 CommonFunc 和 DynamicLLMService 中各出现一次。需要重构AI服务调用层，消除分散和重复。
