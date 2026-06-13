package com.linkyoyo.reportaudit.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * Azure OpenAI SDK connection properties.
 * Used by CommonFunc's SDK-based methods (CallOpenAiBySse, callOpenAi, callNewOpenAi).
 */
@Configuration
public class AzureOpenAiProperties {

    @Value("${azure.openai.endpoint}")
    private String endpoint;

    @Value("${azure.openai.key}")
    private String key;

    public String getEndpoint() {
        return endpoint;
    }

    public String getKey() {
        return key;
    }
}
