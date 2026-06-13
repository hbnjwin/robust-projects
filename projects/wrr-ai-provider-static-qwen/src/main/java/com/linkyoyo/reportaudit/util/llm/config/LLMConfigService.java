package com.linkyoyo.reportaudit.util.llm.config;

import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.config.LinkyoyoAiConfig;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * LLM配置桥接服务
 * 从现有的AiConfig和LinkyoyoAiConfig读取配置，构建统一的LLMAgentConfig
 */
@Service
@Slf4j
public class LLMConfigService {

    @Autowired
    private AiConfig aiConfig;

    @Autowired
    private LinkyoyoAiConfig linkyoyoAiConfig;

    @Value("${ai.service.active-provider:azure_openai}")
    private String activeProviderValue;

    private volatile LLMAgentConfig cachedConfig;

    /**
     * 获取当前LLM代理配置（带缓存）
     */
    public LLMAgentConfig getLLMConfig() {
        if (cachedConfig == null) {
            synchronized (this) {
                if (cachedConfig == null) {
                    cachedConfig = buildAgentConfig();
                }
            }
        }
        return cachedConfig;
    }

    /**
     * 获取当前提供商类型
     */
    public LLMProviderType getCurrentProvider() {
        return getLLMConfig().getEffect();
    }

    /**
     * 清除配置缓存，强制下次重新构建
     */
    public void clearCache() {
        cachedConfig = null;
        log.info("LLM配置缓存已清除");
    }

    private LLMAgentConfig buildAgentConfig() {
        LLMProviderType provider = LLMProviderType.fromValue(activeProviderValue);
        LLMConfig config;

        switch (provider) {
            case AZURE_OPENAI:
                config = buildAzureOpenAIConfig();
                break;
            case OPENAI:
                config = buildOpenAIConfig();
                break;
            case LINKYOYO_AGENT:
                config = buildLinkyoyoAgentConfig();
                break;
            default:
                throw new IllegalStateException("不支持的提供商: " + provider);
        }

        LLMAgentConfig agentConfig = new LLMAgentConfig();
        agentConfig.setEffect(provider);
        agentConfig.setActiveConfig(config);

        log.info("构建LLM配置: provider={}, model={}, temperature={}, maxTokens={}",
                provider.getValue(), config.getModel(),
                config.getTemperature(), config.getMaxTokens());

        return agentConfig;
    }

    private AzureOpenAIConfig buildAzureOpenAIConfig() {
        AzureOpenAIConfig config = new AzureOpenAIConfig();
        config.setKey(aiConfig.getKey());
        config.setBaseUrl(aiConfig.getUrl());
        config.setModel(aiConfig.getModel());
        config.setApiVersion(aiConfig.getVersion());
        config.setTemperature(0.7f);
        config.setMaxTokens(4096);
        return config;
    }

    private OpenAIConfig buildOpenAIConfig() {
        OpenAIConfig config = new OpenAIConfig();
        config.setKey(aiConfig.getDeepseekKey());
        config.setChatCompletionsUrl(aiConfig.getDeepseekUrl());
        config.setModel(aiConfig.getDeepseekModel());
        config.setTemperature(0.7f);
        config.setMaxTokens(4096);
        return config;
    }

    private LinkyoyoAgentConfig buildLinkyoyoAgentConfig() {
        LinkyoyoAgentConfig config = new LinkyoyoAgentConfig();
        config.setToken(linkyoyoAiConfig.getToken());
        config.setUrl(linkyoyoAiConfig.getUrl());
        config.setModel("gpt-4o-5");
        config.setTemperature(0f);
        config.setMaxTokens(4096);
        return config;
    }
}
