package com.linkyoyo.reportaudit.util.llm.config;

/**
 * LLM配置抽象基类
 * 包含所有提供商共用的配置属性
 */
public abstract class LLMConfig {

    private String model;
    private Float temperature = 0.7f;
    private Integer maxTokens = 4096;

    public String getModel() {
        return model;
    }

    public void setModel(String model) {
        this.model = model;
    }

    public Float getTemperature() {
        return temperature;
    }

    public void setTemperature(Float temperature) {
        this.temperature = temperature;
    }

    public Integer getMaxTokens() {
        return maxTokens;
    }

    public void setMaxTokens(Integer maxTokens) {
        this.maxTokens = maxTokens;
    }

    /**
     * 验证配置是否有效
     */
    public boolean isValid() {
        return model != null && !model.isEmpty();
    }
}
