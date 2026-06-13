package com.linkyoyo.reportaudit.util.llm.config;

import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.config.LinkyoyoAiConfig;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.EnumMap;
import java.util.Map;

@Service
@Slf4j
public class LLMConfigService {

    private final AiConfig aiConfig;
    private final LinkyoyoAiConfig linkyoyoAiConfig;
    private volatile Map<LLMProviderType, LLMProviderConfig> configCache;

    @Autowired
    public LLMConfigService(AiConfig aiConfig, LinkyoyoAiConfig linkyoyoAiConfig) {
        this.aiConfig = aiConfig;
        this.linkyoyoAiConfig = linkyoyoAiConfig;
    }

    public Map<LLMProviderType, LLMProviderConfig> getAllConfigs() {
        if (configCache == null) {
            synchronized (this) {
                if (configCache == null) {
                    configCache = buildConfigs();
                }
            }
        }
        return configCache;
    }

    public LLMProviderConfig getConfig(LLMProviderType type) {
        return getAllConfigs().get(type);
    }

    public LLMProviderType getDefaultProviderType() {
        if (aiConfig.isAzure()) {
            return LLMProviderType.AZURE_OPENAI;
        }
        return LLMProviderType.OPENAI_COMPATIBLE;
    }

    public LLMProviderConfig getDefaultConfig() {
        return getConfig(getDefaultProviderType());
    }

    public void clearCache() {
        configCache = null;
        log.info("LLM config cache cleared");
    }

    private Map<LLMProviderType, LLMProviderConfig> buildConfigs() {
        Map<LLMProviderType, LLMProviderConfig> configs = new EnumMap<>(LLMProviderType.class);

        // Azure OpenAI
        LLMProviderConfig azureConfig = new LLMProviderConfig();
        azureConfig.setType(LLMProviderType.AZURE_OPENAI);
        azureConfig.setUrl(aiConfig.getUrl());
        azureConfig.setKey(aiConfig.getKey());
        azureConfig.setModel(aiConfig.getModel());
        azureConfig.setApiVersion(aiConfig.getVersion());
        azureConfig.setPrompt(aiConfig.getPrompt());
        azureConfig.setAzure(true);
        azureConfig.setTemperature(0.1f);
        azureConfig.setMaxTokens(8000);
        configs.put(LLMProviderType.AZURE_OPENAI, azureConfig);

        // DeepSeek / OpenAI Compatible
        LLMProviderConfig deepseekConfig = new LLMProviderConfig();
        deepseekConfig.setType(LLMProviderType.OPENAI_COMPATIBLE);
        deepseekConfig.setUrl(aiConfig.getDeepseekUrl());
        deepseekConfig.setKey(aiConfig.getDeepseekKey());
        deepseekConfig.setModel(aiConfig.getDeepseekModel());
        deepseekConfig.setPrompt(aiConfig.getDeepseekPrompt());
        deepseekConfig.setAzure(aiConfig.isDeepseekIsAzure());
        deepseekConfig.setTemperature(0.1f);
        deepseekConfig.setMaxTokens(8000);
        configs.put(LLMProviderType.OPENAI_COMPATIBLE, deepseekConfig);

        // Linkyoyo Agent
        LLMProviderConfig linkyoyoConfig = new LLMProviderConfig();
        linkyoyoConfig.setType(LLMProviderType.LINKYOYO_AGENT);
        linkyoyoConfig.setUrl(linkyoyoAiConfig.getUrl());
        linkyoyoConfig.setKey(linkyoyoAiConfig.getToken());
        linkyoyoConfig.setModel("gpt-4o-5");
        linkyoyoConfig.setTemperature(0f);
        linkyoyoConfig.setMaxTokens(4096);
        configs.put(LLMProviderType.LINKYOYO_AGENT, linkyoyoConfig);

        log.info("LLM configs loaded: {} providers", configs.size());
        return configs;
    }
}
