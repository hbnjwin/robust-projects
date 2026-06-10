package com.linkyoyo.reportaudit.util.llm;

import org.springframework.stereotype.Service;
import java.util.Map;
import java.util.HashMap;

@Service
public class DynamicLLMService {
    private final Map<String, Object> providerConfigs = new HashMap<>();

    public String call(String provider, String prompt) {
        if ("azure".equals(provider)) {
            return callAzureOpenAI(prompt);
        } else if ("deepseek".equals(provider)) {
            return callDeepSeek(prompt);
        }
        throw new RuntimeException("Unknown provider: " + provider);
    }

    private String callAzureOpenAI(String prompt) {
        // Direct HTTP call to Azure OpenAI
        return "";
    }

    private String callDeepSeek(String prompt) {
        // Direct HTTP call to DeepSeek
        return "";
    }
}
