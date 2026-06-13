package com.linkyoyo.reportaudit.util.llm;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.linkyoyo.reportaudit.config.AiServiceConfig;
import com.linkyoyo.reportaudit.util.llm.config.*;
import com.linkyoyo.reportaudit.util.llm.model.LLMMessage;
import com.linkyoyo.reportaudit.util.llm.model.LLMResponse;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 动态LLM服务
 * 根据配置动态选择和调用不同的LLM提供商
 */
@Service
@Slf4j
public class DynamicLLMService {

    @Autowired
    private LLMConfigService configService;

    @Autowired
    private HttpClientFactory httpClientFactory;

    @Autowired
    private AiServiceConfig aiServiceConfig;

    /**
     * 统一的聊天完成接口
     */
    public LLMResponse chatCompletion(List<LLMMessage> messages) {
        return chatCompletion(messages, null, null, null);
    }

    /**
     * 统一的聊天完成接口（带参数）
     */
    public LLMResponse chatCompletion(List<LLMMessage> messages, Float temperature,
                                     Integer maxTokens, String model) {
        try {
            // 获取当前配置
            LLMAgentConfig config = configService.getLLMConfig();
            if (config == null) {
                log.error("LLM配置为null");
                return LLMResponse.error("LLM配置为null");
            }

            if (!config.isActiveConfigValid()) {
                log.error("LLM配置验证失败: provider={}, activeConfig={}",
                    config.getEffect(), config.getActiveConfig());
                return LLMResponse.error("LLM配置验证失败: " + config.getEffect());
            }

            LLMConfig activeConfig = config.getActiveConfig();
            LLMProviderType provider = config.getEffect();

            // 使用传入的参数或配置中的默认值
            temperature = temperature != null ? temperature : activeConfig.getTemperature();
            maxTokens = maxTokens != null ? maxTokens : activeConfig.getMaxTokens();
            model = model != null ? model : activeConfig.getModel();

            log.info("调用LLM服务: provider={}, model={}, temperature={}, maxTokens={}",
                    provider.getValue(), model, temperature, maxTokens);

            // 详细打印LLM调用参数用于调试
            log.info("=== LLM调用详细参数 ===");
            log.info("Provider: {}", provider.getValue());
            log.info("Model: {}", model);
            log.info("Temperature: {}", temperature);
            log.info("MaxTokens: {}", maxTokens);
            log.info("Messages Count: {}", messages.size());
            for (int i = 0; i < messages.size(); i++) {
                LLMMessage msg = messages.get(i);
                log.info("Message {}[{}]: {}", i+1, msg.getRole(),
                    msg.getContent().length() > 300 ? msg.getContent().substring(0, 300) + "..." : msg.getContent());
            }
            log.info("=== 参数详情结束 ===");

            // 根据提供商调用相应的方法
            switch (provider) {
                case AZURE_OPENAI:
                    return callAzureOpenAI(messages, temperature, maxTokens, model, (AzureOpenAIConfig) activeConfig);
                case OPENAI:
                    return callOpenAI(messages, temperature, maxTokens, model, (OpenAIConfig) activeConfig);
                case LINKYOYO_AGENT:
                    return callLinkyoyoAgent(messages, temperature, maxTokens, model, (LinkyoyoAgentConfig) activeConfig);
                default:
                    return LLMResponse.error("不支持的LLM提供商: " + provider.getValue());
            }

        } catch (Exception e) {
            log.error("LLM调用失败: {}", e.getMessage(), e);
            return LLMResponse.error("LLM调用异常: " + e.getMessage());
        }
    }

    /**
     * 调用Azure OpenAI
     */
    private LLMResponse callAzureOpenAI(List<LLMMessage> messages, Float temperature,
                                       Integer maxTokens, String model, AzureOpenAIConfig config) {
        String endpoint = config.buildEndpointUrl();
        if (endpoint == null) {
            return LLMResponse.error("Azure OpenAI端点URL构建失败", "azure_openai");
        }

        // 构建请求头
        Headers.Builder headersBuilder = new Headers.Builder()
            .add("Content-Type", "application/json")
            .add("api-key", config.getKey());

        // 构建请求体
        JSONObject requestJson = buildChatCompletionRequest(messages, temperature, maxTokens, model, false);

        RequestBody requestBody = RequestBody.create(
            MediaType.parse("application/json"),
            requestJson.toString()
        );

        Request request = new Request.Builder()
            .url(endpoint)
            .headers(headersBuilder.build())
            .post(requestBody)
            .build();

        log.info("发送Azure OpenAI请求: {}", endpoint);

        return executeWithRetry(request, "azure_openai");
    }

    /**
     * 调用OpenAI
     */
    private LLMResponse callOpenAI(List<LLMMessage> messages, Float temperature,
                                  Integer maxTokens, String model, OpenAIConfig config) {
        String endpoint = config.getChatCompletionsUrl();

        // 构建请求头
        Headers.Builder headersBuilder = new Headers.Builder()
            .add("Content-Type", "application/json")
            .add("Authorization", "Bearer " + config.getKey());

        // 构建请求体
        JSONObject requestJson = buildChatCompletionRequest(messages, temperature, maxTokens, model, true);

        RequestBody requestBody = RequestBody.create(
            MediaType.parse("application/json"),
            requestJson.toString()
        );

        Request request = new Request.Builder()
            .url(endpoint)
            .headers(headersBuilder.build())
            .post(requestBody)
            .build();

        log.info("发送OpenAI请求: {}", endpoint);

        return executeWithRetry(request, "openai");
    }

    /**
     * 调用Linkyoyo Agent
     */
    private LLMResponse callLinkyoyoAgent(List<LLMMessage> messages, Float temperature,
                                         Integer maxTokens, String model, LinkyoyoAgentConfig config) {
        // 提取用户消息
        String userMessage = extractUserMessage(messages);

        // 构建请求头
        Headers.Builder headersBuilder = new Headers.Builder()
            .add("Content-Type", "application/json")
            .add("Authorization", "Bearer " + config.getToken());

        // 使用共享的请求体构建器
        JSONObject requestJson = LinkyoyoRequestBuilder.buildRequest(
                userMessage, model, temperature, maxTokens);

        RequestBody requestBody = RequestBody.create(
            MediaType.parse("application/json"),
            requestJson.toString()
        );

        Request request = new Request.Builder()
            .url(config.getUrl())
            .headers(headersBuilder.build())
            .post(requestBody)
            .build();

        log.info("发送Linkyoyo Agent请求: {}", config.getUrl());

        return executeLinkyoyoWithRetry(request);
    }

    /**
     * 从消息列表中提取用户消息
     */
    private String extractUserMessage(List<LLMMessage> messages) {
        for (LLMMessage msg : messages) {
            if ("user".equals(msg.getRole())) {
                return msg.getContent();
            }
        }
        // 回退到最后一条消息
        if (!messages.isEmpty()) {
            return messages.get(messages.size() - 1).getContent();
        }
        return "";
    }

    /**
     * 带重试的HTTP执行（OpenAI/Azure OpenAI响应格式）
     */
    private LLMResponse executeWithRetry(Request request, String provider) {
        int maxRetries = aiServiceConfig.isRetryEnabled() ? aiServiceConfig.getMaxRetries() : 1;
        LLMResponse lastResponse = null;

        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            long startTime = System.currentTimeMillis();
            try {
                OkHttpClient client = httpClientFactory.getSharedClient();
                try (Response response = client.newCall(request).execute()) {
                    long elapsed = System.currentTimeMillis() - startTime;
                    if (aiServiceConfig.isSlowResponse(elapsed)) {
                        log.warn("LLM响应缓慢: {}ms (阈值: {}ms), provider={}",
                                elapsed, aiServiceConfig.getSlowResponseThreshold(), provider);
                    }
                    lastResponse = handleChatCompletionResponse(response, provider);
                    if (lastResponse.isSuccess()) {
                        return lastResponse;
                    }
                }
            } catch (Exception e) {
                log.error("{}调用失败 (尝试 {}/{}): {}", provider, attempt, maxRetries, e.getMessage());
            }
            if (attempt < maxRetries) {
                int delay = aiServiceConfig.calculateRetryDelay(attempt);
                log.info("重试延迟: {}ms", delay);
                try {
                    Thread.sleep(delay);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        return lastResponse != null ? lastResponse : LLMResponse.error(provider + "调用失败: 重试耗尽", provider);
    }

    /**
     * 带重试的HTTP执行（Linkyoyo Agent响应格式）
     */
    private LLMResponse executeLinkyoyoWithRetry(Request request) {
        int maxRetries = aiServiceConfig.isRetryEnabled() ? aiServiceConfig.getMaxRetries() : 1;
        LLMResponse lastResponse = null;

        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            long startTime = System.currentTimeMillis();
            try {
                OkHttpClient client = httpClientFactory.getSharedClient();
                try (Response response = client.newCall(request).execute()) {
                    long elapsed = System.currentTimeMillis() - startTime;
                    if (aiServiceConfig.isSlowResponse(elapsed)) {
                        log.warn("Linkyoyo Agent响应缓慢: {}ms (阈值: {}ms)",
                                elapsed, aiServiceConfig.getSlowResponseThreshold());
                    }
                    lastResponse = handleLinkyoyoAgentResponse(response);
                    if (lastResponse.isSuccess()) {
                        return lastResponse;
                    }
                }
            } catch (Exception e) {
                log.error("Linkyoyo Agent调用失败 (尝试 {}/{}): {}", attempt, maxRetries, e.getMessage());
            }
            if (attempt < maxRetries) {
                int delay = aiServiceConfig.calculateRetryDelay(attempt);
                log.info("重试延迟: {}ms", delay);
                try {
                    Thread.sleep(delay);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        return lastResponse != null ? lastResponse : LLMResponse.error("Linkyoyo Agent调用失败: 重试耗尽", "linkyoyo_agent");
    }

    /**
     * 构建聊天完成请求体
     */
    private JSONObject buildChatCompletionRequest(List<LLMMessage> messages, Float temperature,
                                                 Integer maxTokens, String model, boolean includeModel) {
        JSONObject requestJson = new JSONObject();

        if (includeModel) {
            requestJson.set("model", model);
        }

        requestJson.set("temperature", temperature);
        requestJson.set("max_tokens", maxTokens);

        // 构建消息数组
        JSONArray messagesArray = new JSONArray();
        for (LLMMessage msg : messages) {
            JSONObject messageObj = new JSONObject();
            messageObj.set("role", msg.getRole());
            messageObj.set("content", msg.getContent());
            messagesArray.add(messageObj);
        }

        requestJson.set("messages", messagesArray);

        return requestJson;
    }

    /**
     * 处理聊天完成响应
     */
    private LLMResponse handleChatCompletionResponse(Response response, String provider) throws Exception {
        if (response.isSuccessful()) {
            String responseBody = response.body().string();
            log.info("LLM响应成功: provider={}", provider);

            JSONObject jsonResponse = JSONUtil.parseObj(responseBody);

            // 提取响应内容
            String content = jsonResponse.getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .getStr("content");

            // 提取使用情况
            Map<String, Object> usage = null;
            if (jsonResponse.containsKey("usage")) {
                usage = jsonResponse.getJSONObject("usage");
            }

            String model = jsonResponse.getStr("model");

            return LLMResponse.success(content, model, provider, usage);

        } else {
            String errorBody = "";
            try {
                errorBody = response.body().string();
            } catch (Exception e) {
                log.warn("无法读取错误响应体: {}", e.getMessage());
            }

            String errorMsg = String.format("请求失败: %d - %s", response.code(), response.message());
            if (!errorBody.isEmpty()) {
                errorMsg += ", 详情: " + errorBody;
            }

            log.error("LLM请求失败: provider={}, error={}", provider, errorMsg);
            return LLMResponse.error(errorMsg, provider);
        }
    }

    /**
     * 处理Linkyoyo Agent响应
     */
    private LLMResponse handleLinkyoyoAgentResponse(Response response) throws Exception {
        if (response.isSuccessful()) {
            String responseBody = response.body().string();
            log.info("Linkyoyo Agent响应成功");

            JSONObject jsonResponse = JSONUtil.parseObj(responseBody);

            // 解析响应内容
            if (jsonResponse.containsKey("data")) {
                JSONObject data = jsonResponse.getJSONObject("data");
                if (data.containsKey("answer")) {
                    String content = data.getStr("answer");

                    Map<String, Object> usage = null;
                    if (data.containsKey("usage")) {
                        usage = data.getJSONObject("usage");
                    }

                    return LLMResponse.success(content, null, "linkyoyo_agent", usage);
                }
            }

            return LLMResponse.error("Linkyoyo Agent返回格式异常", "linkyoyo_agent");

        } else {
            String errorBody = "";
            try {
                errorBody = response.body().string();
            } catch (Exception e) {
                log.warn("无法读取Linkyoyo Agent错误响应体: {}", e.getMessage());
            }

            String errorMsg = String.format("请求失败: %d - %s", response.code(), response.message());
            if (!errorBody.isEmpty()) {
                errorMsg += ", 详情: " + errorBody;
            }

            log.error("Linkyoyo Agent请求失败: {}", errorMsg);
            return LLMResponse.error(errorMsg, "linkyoyo_agent");
        }
    }

    /**
     * 获取当前激活的提供商
     */
    public String getCurrentProvider() {
        return configService.getCurrentProvider().getValue();
    }

    /**
     * 获取当前激活的模型名称
     */
    public String getActiveModelName() {
        LLMAgentConfig config = configService.getLLMConfig();
        if (config != null && config.getActiveConfig() != null) {
            return config.getActiveConfig().getModel();
        }
        return null;
    }

    /**
     * 刷新配置
     */
    public void refreshConfig() {
        configService.clearCache();
        log.info("LLM配置已刷新");
    }
}
