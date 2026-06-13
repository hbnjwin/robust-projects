package com.linkyoyo.reportaudit.util.llm.config;

/**
 * OpenAI兼容API配置
 * 也适用于DeepSeek等使用相同API格式的提供商
 */
public class OpenAIConfig extends LLMConfig {

    private String key;
    private String chatCompletionsUrl;

    public String getKey() {
        return key;
    }

    public void setKey(String key) {
        this.key = key;
    }

    public String getChatCompletionsUrl() {
        return chatCompletionsUrl;
    }

    public void setChatCompletionsUrl(String chatCompletionsUrl) {
        this.chatCompletionsUrl = chatCompletionsUrl;
    }

    @Override
    public boolean isValid() {
        return super.isValid() && key != null && !key.isEmpty()
                && chatCompletionsUrl != null && !chatCompletionsUrl.isEmpty();
    }
}
