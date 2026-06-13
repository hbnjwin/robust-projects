package com.linkyoyo.reportaudit.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * Linkyoyo AI 配置类
 */
@Configuration
public class LinkyoyoAiConfig {

    @Value("${linkyoyo_ai.url:https://ai-verify.bluecloudatlas.cn/gateway/hcmsp-ai-keystone/api/chat-messages}")
    private String url;

    @Value("${linkyoyo_ai.token:eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJmNzU1MTBkMi1iYWZiLTQwZGMtYWQ1Yi03NGFjNmFiODdiN2YiLCJzdWIiOiJXZWIgQVBJIFBhc3Nwb3J0IiwiYXBwX2lkIjoiZjc1NTEwZDItYmFmYi00MGRjLWFkNWItNzRhYzZhYjg3YjdmIiwiYXBwX2NvZGUiOiJhZnVibng3cGdkQU05b042IiwiZW5kX3VzZXJfaWQiOjExMiwicGhvbmUiOiIxNzgwMjk2ODg1OCIsImludGVybmFsIjp0cnVlfQ.-59ZVl0hKSN7-3gdMyCjT-r5Vz3TqULMjd9Xq-guyFY}")
    private String token;

    @Value("${linkyoyo_ai.aiType:0}")
    private Integer aiType;

    public String getUrl() {
        return url;
    }

    public String getToken() {
        return token;
    }

    public Integer getAiType() {
        return aiType;
    }
}
