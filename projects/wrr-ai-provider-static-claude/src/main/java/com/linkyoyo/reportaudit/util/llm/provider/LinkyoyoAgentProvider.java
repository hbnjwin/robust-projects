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

@Component
@Slf4j
public class LinkyoyoAgentProvider implements LLMProvider {

    private final SecureHttpClientFactory httpClientFactory;

    @Autowired
    public LinkyoyoAgentProvider(SecureHttpClientFactory httpClientFactory) {
        this.httpClientFactory = httpClientFactory;
    }

    @Override
    public LLMProviderType getType() {
        return LLMProviderType.LINKYOYO_AGENT;
    }

    @Override
    public LLMResponse chatCompletion(List<LLMMessage> messages, LLMProviderConfig config,
                                      Float temperature, Integer maxTokens, String model) {
        try {
            String query = extractUserQuery(messages);
            float temp = temperature != null ? temperature : config.getTemperature();
            int tokens = maxTokens != null ? maxTokens : config.getMaxTokens();
            String modelName = model != null ? model : config.getModel();

            log.info("Linkyoyo Agent request: {}, model: {}", config.getUrl(), modelName);
            JSONObject requestJson = buildLinkyoyoAgentRequest(query, temp, tokens, modelName);
            RequestBody requestBody = RequestBody.create(
                    MediaType.parse("application/json; charset=utf-8"), requestJson.toString());
            Request request = new Request.Builder()
                    .url(config.getUrl())
                    .header("Authorization", "Bearer " + config.getKey())
                    .post(requestBody)
                    .build();
            try (Response response = httpClientFactory.getClient().newCall(request).execute()) {
                return handleResponse(response);
            }
        } catch (Exception e) {
            log.error("Linkyoyo Agent call failed: {}", e.getMessage(), e);
            return LLMResponse.error("Linkyoyo Agent call failed: " + e.getMessage(), getType().getValue());
        }
    }

    private String extractUserQuery(List<LLMMessage> messages) {
        for (LLMMessage msg : messages) {
            if ("user".equals(msg.getRole())) {
                return msg.getContent();
            }
        }
        if (!messages.isEmpty()) {
            return messages.get(messages.size() - 1).getContent();
        }
        return "";
    }

    private JSONObject buildLinkyoyoAgentRequest(String query, float temperature,
                                                 int maxTokens, String model) {
        JSONObject modelCompletionParams = new JSONObject();
        modelCompletionParams.set("frequency_penalty", 0);
        modelCompletionParams.set("max_tokens", maxTokens);
        modelCompletionParams.set("presence_penalty", 0);
        modelCompletionParams.set("stop", new String[]{});
        modelCompletionParams.set("temperature", temperature);
        modelCompletionParams.set("top_p", 1);

        JSONObject modelDef = new JSONObject();
        modelDef.set("completion_params", modelCompletionParams);
        modelDef.set("is_system", true);
        modelDef.set("mode", "chat");
        modelDef.set("name", model);
        modelDef.set("provider", "azure_openai");
        modelDef.set("vision", true);

        JSONObject imageConfig = new JSONObject();
        imageConfig.set("detail", "high");
        imageConfig.set("enabled", false);
        imageConfig.set("number_limits", 3);
        imageConfig.set("transfer_methods", new String[]{"remote_url", "local_file"});

        JSONObject fileUploadConfig = new JSONObject();
        fileUploadConfig.set("image", imageConfig);

        JSONObject systemParameters = new JSONObject();
        systemParameters.set("audio_file_size_limit", 50);
        systemParameters.set("file_size_limit", 25);
        systemParameters.set("image_file_size_limit", 10);
        systemParameters.set("video_file_size_limit", 100);
        systemParameters.set("workflow_file_upload_limit", 10);

        JSONObject textToSpeech = new JSONObject();
        textToSpeech.set("enabled", false);
        textToSpeech.set("language", "");
        textToSpeech.set("voice", "");

        JSONObject userAppConfig = new JSONObject();
        userAppConfig.set("multiple_rounds_of_dialogue", false);
        userAppConfig.set("public_domain_dataset", false);
        userAppConfig.set("personal_domain_dataset", false);
        userAppConfig.set("index_enhance", false);

        JSONObject modelConfigObj = new JSONObject();
        modelConfigObj.set("annotation_reply", new JSONObject().set("enabled", false));
        modelConfigObj.set("file_upload", fileUploadConfig);
        modelConfigObj.set("index_enhance_config", null);
        modelConfigObj.set("model", modelDef);
        modelConfigObj.set("more_like_this", new JSONObject().set("enabled", false));
        modelConfigObj.set("opening_statement", "");
        modelConfigObj.set("retriever_resource", new JSONObject().set("enabled", false));
        modelConfigObj.set("sensitive_word_avoidance", new JSONObject().set("enabled", false));
        modelConfigObj.set("speech_to_text", new JSONObject().set("enabled", false));
        modelConfigObj.set("suggested_questions", new String[]{});
        modelConfigObj.set("suggested_questions_after_answer", new JSONObject().set("enabled", false));
        modelConfigObj.set("system_parameters", systemParameters);
        modelConfigObj.set("text_to_speech", textToSpeech);
        modelConfigObj.set("url_format", null);
        modelConfigObj.set("user_input_form", new String[]{});
        modelConfigObj.set("userAppConfig", userAppConfig);

        JSONObject requestJson = new JSONObject();
        requestJson.set("model_config", modelConfigObj);
        requestJson.set("response_mode", "blocking");
        requestJson.set("inputs", new JSONObject());
        requestJson.set("query", query);
        requestJson.set("conversation_id", "");
        requestJson.set("files", new String[]{});
        requestJson.set("custom_files", new String[]{});
        requestJson.set("file_read_info", null);
        requestJson.set("open_internet", false);

        return requestJson;
    }

    private LLMResponse handleResponse(Response response) throws Exception {
        if (response.isSuccessful()) {
            String responseBody = response.body().string();
            log.info("Linkyoyo Agent response success");
            JSONObject jsonResponse = JSONUtil.parseObj(responseBody);
            if (jsonResponse.containsKey("data")) {
                JSONObject data = jsonResponse.getJSONObject("data");
                if (data.containsKey("answer")) {
                    String content = data.getStr("answer");
                    Map<String, Object> usage = null;
                    if (data.containsKey("usage")) {
                        usage = data.getJSONObject("usage");
                    }
                    return LLMResponse.success(content, null, getType().getValue(), usage);
                }
            }
            return LLMResponse.error("Linkyoyo Agent unexpected response format", getType().getValue());
        } else {
            String errorBody = "";
            try {
                errorBody = response.body().string();
            } catch (Exception e) {
                log.warn("Cannot read error response body: {}", e.getMessage());
            }
            String errorMsg = String.format("Request failed: %d - %s, details: %s",
                    response.code(), response.message(), errorBody);
            log.error("Linkyoyo Agent request failed: {}", errorMsg);
            return LLMResponse.error(errorMsg, getType().getValue());
        }
    }
}
