package com.linkyoyo.reportaudit.util.llm.config;

/**
 * LLM提供商类型枚举
 */
public enum LLMProviderType {
    AZURE_OPENAI("azure_openai"),
    OPENAI("openai"),
    LINKYOYO_AGENT("linkyoyo_agent");

    private final String value;

    LLMProviderType(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }

    public static LLMProviderType fromValue(String value) {
        for (LLMProviderType type : values()) {
            if (type.value.equalsIgnoreCase(value)) {
                return type;
            }
        }
        throw new IllegalArgumentException("未知的LLM提供商类型: " + value);
    }
}
