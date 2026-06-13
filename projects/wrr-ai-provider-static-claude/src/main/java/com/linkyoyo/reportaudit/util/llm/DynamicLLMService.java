package com.linkyoyo.reportaudit.util.llm;

import com.linkyoyo.reportaudit.util.llm.config.LLMConfigService;
import com.linkyoyo.reportaudit.util.llm.config.LLMProviderConfig;
import com.linkyoyo.reportaudit.util.llm.config.LLMProviderType;
import com.linkyoyo.reportaudit.util.llm.model.LLMMessage;
import com.linkyoyo.reportaudit.util.llm.model.LLMResponse;
import com.linkyoyo.reportaudit.util.llm.provider.LLMProvider;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

/**
 * Unified LLM service.
 * Uses provider registry (strategy pattern) instead of switch-case dispatch.
 * All HTTP client, SSL, and request-building logic lives in providers and SecureHttpClientFactory.
 */
@Service
@Slf4j
public class DynamicLLMService {

    private final LLMConfigService configService;
    private final Map<LLMProviderType, LLMProvider> providerRegistry;

    @Autowired
    public DynamicLLMService(LLMConfigService configService, List<LLMProvider> providers) {
        this.configService = configService;
        this.providerRegistry = new EnumMap<>(LLMProviderType.class);
        for (LLMProvider provider : providers) {
            providerRegistry.put(provider.getType(), provider);
            log.info("Registered LLM provider: {}", provider.getType().getValue());
        }
    }

    public LLMResponse chatCompletion(List<LLMMessage> messages) {
        return chatCompletion(messages, null, null, null, null);
    }

    public LLMResponse chatCompletion(List<LLMMessage> messages, LLMProviderType providerType) {
        return chatCompletion(messages, providerType, null, null, null);
    }

    public LLMResponse chatCompletion(List<LLMMessage> messages, LLMProviderType providerType,
                                      Float temperature, Integer maxTokens, String model) {
        try {
            if (providerType == null) {
                providerType = configService.getDefaultProviderType();
            }

            LLMProvider provider = providerRegistry.get(providerType);
            if (provider == null) {
                String error = "No provider registered for type: " + providerType.getValue();
                log.error(error);
                return LLMResponse.error(error);
            }

            LLMProviderConfig config = configService.getConfig(providerType);
            if (config == null || !config.isValid()) {
                String error = "Invalid config for provider: " + providerType.getValue();
                log.error(error);
                return LLMResponse.error(error);
            }

            log.info("LLM call: provider={}, model={}", providerType.getValue(),
                    model != null ? model : config.getModel());

            return provider.chatCompletion(messages, config, temperature, maxTokens, model);

        } catch (Exception e) {
            log.error("LLM call failed: {}", e.getMessage(), e);
            return LLMResponse.error("LLM call exception: " + e.getMessage());
        }
    }

    public String getCurrentProvider() {
        return configService.getDefaultProviderType().getValue();
    }

    public String getActiveModelName() {
        LLMProviderConfig config = configService.getDefaultConfig();
        return config != null ? config.getModel() : null;
    }

    public void refreshConfig() {
        configService.clearCache();
        log.info("LLM config refreshed");
    }
}
