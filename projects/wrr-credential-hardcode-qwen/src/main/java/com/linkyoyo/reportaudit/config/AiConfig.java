package com.linkyoyo.reportaudit.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * AI服务配置 - Azure OpenAI 和 DeepSeek
 * 所有敏感凭证通过外部配置（application.yml / 环境变量）注入，
 * 不在代码中硬编码。
 */
@Configuration
public class AiConfig {

    // --- Azure OpenAI primary (CallOpenAiBySse / callOpenAi / callNewOpenAi) ---
    @Value("${ai.azure.endpoint:}")
    private String azureEndpoint;

    @Value("${ai.azure.key:}")
    private String azureKey;

    @Value("${ai.azure.service-version:2024-05-01-preview}")
    private String azureServiceVersion;

    @Value("${ai.azure.deployment-sse:gpt-4o-mini}")
    private String azureDeploymentSse;

    @Value("${ai.azure.deployment:gpt-4o-mini}")
    private String azureDeployment;

    @Value("${ai.azure.deployment-new:us-east-gpt4o}")
    private String azureDeploymentNew;

    // --- Azure OpenAI fallback (callAiWithOkHttp) ---
    @Value("${ai.azure-fallback.url:}")
    private String azureFallbackUrl;

    @Value("${ai.azure-fallback.key:}")
    private String azureFallbackKey;

    @Value("${ai.azure-fallback.model:gpt-4o-5}")
    private String azureFallbackModel;

    @Value("${ai.azure-fallback.version:2024-05-01-preview}")
    private String azureFallbackVersion;

    @Value("${ai.azure-fallback.prompt:}")
    private String azureFallbackPrompt;

    // --- DeepSeek (callDeepSeekAi) ---
    @Value("${ai.deepseek.url:}")
    private String deepseekUrl;

    @Value("${ai.deepseek.key:}")
    private String deepseekKey;

    @Value("${ai.deepseek.model:deepseek-chat}")
    private String deepseekModel;

    @Value("${ai.deepseek.prompt:}")
    private String deepseekPrompt;

    @Value("${ai.deepseek.is-azure:false}")
    private boolean deepseekIsAzure;

    // --- Getters ---

    public String getAzureEndpoint() {
        return azureEndpoint;
    }

    public String getAzureKey() {
        return azureKey;
    }

    public String getAzureServiceVersion() {
        return azureServiceVersion;
    }

    public String getAzureDeploymentSse() {
        return azureDeploymentSse;
    }

    public String getAzureDeployment() {
        return azureDeployment;
    }

    public String getAzureDeploymentNew() {
        return azureDeploymentNew;
    }

    /** callAiWithOkHttp 无参版本判断是否走 Azure */
    public boolean isAzure() {
        return azureFallbackUrl != null && !azureFallbackUrl.isEmpty();
    }

    public String getUrl() {
        return azureFallbackUrl;
    }

    public String getKey() {
        return azureFallbackKey;
    }

    public String getModel() {
        return azureFallbackModel;
    }

    public String getVersion() {
        return azureFallbackVersion;
    }

    public String getPrompt() {
        return azureFallbackPrompt;
    }

    public boolean isDeepseekIsAzure() {
        return deepseekIsAzure;
    }

    public String getDeepseekUrl() {
        return deepseekUrl;
    }

    public String getDeepseekKey() {
        return deepseekKey;
    }

    public String getDeepseekModel() {
        return deepseekModel;
    }

    public String getDeepseekPrompt() {
        return deepseekPrompt;
    }
}
