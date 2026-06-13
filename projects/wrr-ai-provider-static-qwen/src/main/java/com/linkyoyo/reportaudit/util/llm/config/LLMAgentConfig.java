package com.linkyoyo.reportaudit.util.llm.config;

/**
 * LLM代理配置
 * 将提供商类型与其对应的配置关联
 */
public class LLMAgentConfig {

    private LLMProviderType effect;
    private LLMConfig activeConfig;

    public LLMProviderType getEffect() {
        return effect;
    }

    public void setEffect(LLMProviderType effect) {
        this.effect = effect;
    }

    public LLMConfig getActiveConfig() {
        return activeConfig;
    }

    public void setActiveConfig(LLMConfig activeConfig) {
        this.activeConfig = activeConfig;
    }

    /**
     * 验证当前活跃配置是否有效
     */
    public boolean isActiveConfigValid() {
        return activeConfig != null && activeConfig.isValid();
    }
}
