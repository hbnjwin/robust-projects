package com.linkyoyo.reportaudit.util.llm.config;

/**
 * Azure OpenAI配置
 */
public class AzureOpenAIConfig extends LLMConfig {

    private String key;
    private String baseUrl;
    private String apiVersion = "2024-05-01-preview";

    public String getKey() {
        return key;
    }

    public void setKey(String key) {
        this.key = key;
    }

    public String getBaseUrl() {
        return baseUrl;
    }

    public void setBaseUrl(String baseUrl) {
        this.baseUrl = baseUrl;
    }

    public String getApiVersion() {
        return apiVersion;
    }

    public void setApiVersion(String apiVersion) {
        this.apiVersion = apiVersion;
    }

    /**
     * 构建Azure OpenAI端点URL
     * 格式: {baseUrl}/openai/deployments/{model}/chat/completions?api-version={version}
     */
    public String buildEndpointUrl() {
        if (baseUrl == null || getModel() == null) {
            return null;
        }
        String base = baseUrl.endsWith("/") ? baseUrl : baseUrl + "/";
        return base + "openai/deployments/" + getModel()
                + "/chat/completions?api-version=" + apiVersion;
    }

    @Override
    public boolean isValid() {
        return super.isValid() && key != null && !key.isEmpty()
                && baseUrl != null && !baseUrl.isEmpty();
    }
}
