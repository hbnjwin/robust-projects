package com.linkyoyo.reportaudit.util.llm;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.linkyoyo.reportaudit.util.llm.config.*;
import com.linkyoyo.reportaudit.util.llm.model.LLMMessage;
import com.linkyoyo.reportaudit.util.llm.model.LLMResponse;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 动态LLM服务
 * 根据配置动态选择和调用不同的LLM提供商
 * 
 * @author AI Assistant
 * @date 2025-01-13
 */
@Service
@Slf4j
public class DynamicLLMService {
    
    @Autowired
    private LLMConfigService configService;
    
    private OkHttpClient httpClient;
    
    public DynamicLLMService() {
        initHttpClient();
    }
    
    /**
     * 初始化HTTP客户端
     */
    private void initHttpClient() {
        try {
            // 创建信任所有证书的TrustManager
            final TrustManager[] trustAllCerts = new TrustManager[] {
                new X509TrustManager() {
                    @Override
                    public void checkClientTrusted(java.security.cert.X509Certificate[] chain, String authType) {}
                    
                    @Override
                    public void checkServerTrusted(java.security.cert.X509Certificate[] chain, String authType) {}
                    
                    @Override
                    public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                        return new java.security.cert.X509Certificate[]{};
                    }
                }
            };
            
            // 创建SSLContext
            final SSLContext sslContext = SSLContext.getInstance("SSL");
            sslContext.init(null, trustAllCerts, new java.security.SecureRandom());
            
            // 创建OkHttpClient
            this.httpClient = new OkHttpClient.Builder()
                .sslSocketFactory(sslContext.getSocketFactory(), (X509TrustManager) trustAllCerts[0])
                .hostnameVerifier((hostname, session) -> true)
                .connectTimeout(60, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .build();
                
        } catch (Exception e) {
            log.error("初始化HTTP客户端失败: {}", e.getMessage(), e);
            // 使用默认客户端
            this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(60, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .build();
        }
    }
    
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
        try {
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
            
            // 执行请求
            try (Response response = httpClient.newCall(request).execute()) {
                return handleChatCompletionResponse(response, "azure_openai");
            }
            
        } catch (Exception e) {
            log.error("Azure OpenAI调用失败: {}", e.getMessage(), e);
            return LLMResponse.error("Azure OpenAI调用失败: " + e.getMessage(), "azure_openai");
        }
    }
    
    /**
     * 调用OpenAI
     */
    private LLMResponse callOpenAI(List<LLMMessage> messages, Float temperature, 
                                  Integer maxTokens, String model, OpenAIConfig config) {
        try {
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
            
            // 执行请求
            try (Response response = httpClient.newCall(request).execute()) {
                return handleChatCompletionResponse(response, "openai");
            }
            
        } catch (Exception e) {
            log.error("OpenAI调用失败: {}", e.getMessage(), e);
            return LLMResponse.error("OpenAI调用失败: " + e.getMessage(), "openai");
        }
    }
    
    /**
     * 调用Linkyoyo Agent
     */
    private LLMResponse callLinkyoyoAgent(List<LLMMessage> messages, Float temperature, 
                                         Integer maxTokens, String model, LinkyoyoAgentConfig config) {
        try {
            // 提取用户消息
            String userMessage = "";
            for (LLMMessage msg : messages) {
                if ("user".equals(msg.getRole())) {
                    userMessage = msg.getContent();
                    break;
                }
            }
            
            if (userMessage.isEmpty() && !messages.isEmpty()) {
                userMessage = messages.get(messages.size() - 1).getContent();
            }
            
            // 构建请求头
            Headers.Builder headersBuilder = new Headers.Builder()
                .add("Content-Type", "application/json")
                .add("Authorization", "Bearer " + config.getToken());
            
            // 构建请求体（参考CommonFunc.callAi方法的格式）
            JSONObject requestJson = buildLinkyoyoAgentRequest(userMessage, temperature, maxTokens, model);
            
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
            
            // 执行请求
            try (Response response = httpClient.newCall(request).execute()) {
                return handleLinkyoyoAgentResponse(response);
            }
            
        } catch (Exception e) {
            log.error("Linkyoyo Agent调用失败: {}", e.getMessage(), e);
            return LLMResponse.error("Linkyoyo Agent调用失败: " + e.getMessage(), "linkyoyo_agent");
        }
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
     * 构建Linkyoyo Agent请求体（参考CommonFunc.callAi方法）
     */
    private JSONObject buildLinkyoyoAgentRequest(String query, Float temperature, Integer maxTokens, String model) {
        JSONObject requestJson = new JSONObject();
        
        // 模型完成参数
        JSONObject modelCompletionParams = new JSONObject();
        modelCompletionParams.set("frequency_penalty", 0);
        modelCompletionParams.set("max_tokens", maxTokens);
        modelCompletionParams.set("presence_penalty", 0);
        modelCompletionParams.set("stop", new String[]{});
        modelCompletionParams.set("temperature", temperature);
        modelCompletionParams.set("top_p", 1);
        
        // 模型配置
        JSONObject modelConfig = new JSONObject();
        modelConfig.set("completion_params", modelCompletionParams);
        modelConfig.set("is_system", true);
        modelConfig.set("mode", "chat");
        modelConfig.set("name", model);
        modelConfig.set("provider", "azure_openai");
        modelConfig.set("vision", true);
        
        // 图像配置
        JSONObject imageConfig = new JSONObject();
        imageConfig.set("detail", "high");
        imageConfig.set("enabled", false);
        imageConfig.set("number_limits", 3);
        imageConfig.set("transfer_methods", new String[]{"remote_url", "local_file"});
        
        JSONObject fileUploadConfig = new JSONObject();
        fileUploadConfig.set("image", imageConfig);
        
        // 系统参数
        JSONObject systemParameters = new JSONObject();
        systemParameters.set("audio_file_size_limit", 50);
        systemParameters.set("file_size_limit", 25);
        systemParameters.set("image_file_size_limit", 10);
        systemParameters.set("video_file_size_limit", 100);
        systemParameters.set("workflow_file_upload_limit", 10);
        
        // 文本转语音
        JSONObject textToSpeech = new JSONObject();
        textToSpeech.set("enabled", false);
        textToSpeech.set("language", "");
        textToSpeech.set("voice", "");
        
        // 用户应用配置
        JSONObject userAppConfig = new JSONObject();
        userAppConfig.set("multiple_rounds_of_dialogue", false);
        userAppConfig.set("public_domain_dataset", false);
        userAppConfig.set("personal_domain_dataset", false);
        userAppConfig.set("index_enhance", false);
        
        // 模型配置对象
        JSONObject modelConfigObj = new JSONObject();
        modelConfigObj.set("annotation_reply", new JSONObject().set("enabled", false));
        modelConfigObj.set("file_upload", fileUploadConfig);
        modelConfigObj.set("index_enhance_config", null);
        modelConfigObj.set("model", modelConfig);
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
        
        // 主请求体
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
