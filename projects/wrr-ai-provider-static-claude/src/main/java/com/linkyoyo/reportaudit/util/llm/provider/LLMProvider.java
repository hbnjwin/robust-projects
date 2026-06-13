package com.linkyoyo.reportaudit.util.llm.provider;

import com.linkyoyo.reportaudit.util.llm.config.LLMProviderConfig;
import com.linkyoyo.reportaudit.util.llm.config.LLMProviderType;
import com.linkyoyo.reportaudit.util.llm.model.LLMMessage;
import com.linkyoyo.reportaudit.util.llm.model.LLMResponse;

import java.util.List;

/**
 * LLM提供商策略接口
 * 每种AI服务实现此接口，由DynamicLLMService通过注册表调度
 */
public interface LLMProvider {

    /**
     * 返回此提供商的类型标识
     */
    LLMProviderType getType();

    /**
     * 执行聊天完成调用
     *
     * @param messages    消息列表
     * @param config      提供商配置
     * @param temperature 温度参数（可为null使用配置默认值）
     * @param maxTokens   最大token数（可为null使用配置默认值）
     * @param model       模型名（可为null使用配置默认值）
     * @return LLM响应
     */
    LLMResponse chatCompletion(List<LLMMessage> messages, LLMProviderConfig config,
                               Float temperature, Integer maxTokens, String model);
}
