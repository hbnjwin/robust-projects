# wrr-credential-hardcode

## Question ID: l1-142

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: claude

## Query

项目中有多处将 API 密钥和服务端点URL直接写在了 Java 源代码里。CommonFunc 类中至少有三处硬编码了 Azure OpenAI 的 AzureKeyCredential 和 endpoint URL（分别在调用 CallOpenAiBySse、CallOpenAi、callNewOpenAi 等方法中），还有 DeepSeek 的 API 密钥和一组备用的 Azure 端点及密钥也写在代码中。此外 BlueCloudAiConfig 的 @Value 注解在默认值里嵌入了完整的 Bearer JWT 令牌和生产环境的 API URL。Linkyoyo Agent 的上传和聊天接口URL也硬编码在 CommonFunc 的 callAi 方法中。这些凭证都随代码提交到了版本控制仓库。需要将所有硬编码的凭证和端点提取到外部配置中。
