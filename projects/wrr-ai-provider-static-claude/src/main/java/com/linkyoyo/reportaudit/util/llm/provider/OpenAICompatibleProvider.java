package com.linkyoyo.reportaudit.util.llm.provider;

import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.linkyoyo.reportaudit.util.llm.config.LLMProviderConfig;
import com.linkyoyo.reportaudit.util.llm.config.LLMProviderType;
import com.linkyoyo.reportaudit.util.llm.http.SecureHttpClientFactory;
import com.linkyoyo.reportaudit.util.llm.model.LLMMessage;
import com.linkyoyo.reportaudit.util.llm.model.LLMResponse;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * OpenAI兼容API提供商（DeepSeek等）
 * 整合原CommonFunc中callDeepSeekAi和callAiWithOkHttp(非Azure路径)
 */
@Component
@Slf4j
public class OpenAICompatibleProvider implements LLMProvider {

    private final SecureHttpClientFactory httpClientFactory;

    @Autowired
    public OpenAICompatibleProvider(SecureHttpClientFactory httpClientFactory) {
        this.httpClientFactory = httpClientFactory;
    }

    @Override
    public LLMProviderType getType() {
        return LLMProviderType.OPENAI_COMPATIBLE;
    }

    @Override
    public LLMResponse chatCompletion(List<LLMMessage> messages, LLMProviderConfig config,
                                      Float temperature, Integer maxTokens, String model) {
        try {
            float temp = temperature != null ? temperature : config.getTemperature();
            int tokens = maxTokens != null ? maxTokens : config.getMaxTokens();
            String modelName = model != null ? model : config.getModel();

            String endpoint = config.getUrl();
            log.info("请求OpenAI Compatible端点: {}, model: {}", endpoint, modelName);

            // 构建请求体（标准OpenAI格式，需要model字段）
            JSONObject requestJson = buildRequestBody(messages, temp, tokens, modelName);

            RequestBody requestBody = RequestBody.create(
                    MediaType.parse("application/json"), requestJson.toString());

            Request request = new Request.Builder()
                    .url(endpoint)
                    .addHeader("Content-Type", "application/json")
                    .addHeader("Authorization", "Bearer " + config.getKey())
                    .post(requestBody)
                    .build();

            try (Response response = httpClientFactory.getClient().newCall(request).execute()) {
                return handleResponse(response);
            }

        } catch (Exception e) {
            log.error("OpenAI Compatible调用失败: {}", e.getMessage(), e);
            return LLMResponse.error("OpenAI Compatible调用失败: " + e.getMessage(), getType().getValue());
        }
    }

    private JSONObject buildRequestBody(List<LLMMessage> messages, float temperature,
                                        int maxTokens, String model) {
        JSONObject requestJson = new JSONObject();
        requestJson.set("model", model);
        requestJson.set("temperature", temperature);
        requestJson.set("max_tokens", maxTokens);

        cn.hutool.json.JSONArray messagesArray = new cn.hutool.json.JSONArray();
        for (LLMMessage msg : messages) {
            JSONObject messageObj = new JSONObject();
            messageObj.set("role", msg.getRole());
            messageObj.set("content", msg.getContent());
            messagesArray.add(messageObj);
        }
        requestJson.set("messages", messagesArray);

        return requestJson;
    }

    private LLMResponse handleResponse(Response response) throws Exception {
        if (response.isSuccessful()) {
            String responseBody = response.body().string();
            log.info("OpenAI Compatible响应成功");

            JSONObject jsonResponse = JSONUtil.parseObj(responseBody);
            String content = jsonResponse.getJSONArray("choices")
                    .getJSONObject(0)
                    .getJSONObject("message")
                    .getStr("content");

            Map<String, Object> usage = null;
            if (jsonResponse.containsKey("usage")) {
                usage = jsonResponse.getJSONObject("usage");
            }

            String model = jsonResponse.getStr("model");
            return LLMResponse.success(content, model, getType().getValue(), usage);
        } else {
            String errorBody = "";
            try {
                errorBody = response.body().string();
            } catch (Exception e) {
                log.warn("无法读取错误响应体: {}", e.getMessage());
            }

            String errorMsg = String.format("请求失败: %d - %s, 详情: %s",
                    response.code(), response.message(), errorBody);
            log.error("OpenAI Compatible请求失败: {}", errorMsg);
            return LLMResponse.error(errorMsg, getType().getValue());
        }
    }
}
