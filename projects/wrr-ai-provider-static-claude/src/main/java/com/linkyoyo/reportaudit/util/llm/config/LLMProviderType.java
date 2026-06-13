package com.linkyoyo.reportaudit.util.llm.config;

public enum LLMProviderType {

    AZURE_OPENAI("azure_openai"),
    OPENAI_COMPATIBLE("openai_compatible"),
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
        throw new IllegalArgumentException("Unknown LLM provider type: " + value);
    }
}
