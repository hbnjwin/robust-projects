package com.linkyoyo.reportaudit.support;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.azure.ai.openai.OpenAIClient;
import com.azure.ai.openai.OpenAIClientBuilder;
import com.azure.ai.openai.OpenAIServiceVersion;
import com.azure.ai.openai.models.*;
import com.azure.core.credential.AzureKeyCredential;
import com.azure.core.util.IterableStream;
import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.config.LinkyoyoAiConfig;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.io.File;
import java.util.*;
import java.util.concurrent.TimeUnit;

@Service
@Slf4j
public class AiService {

    @Autowired
    private AiConfig aiConfig;

    @Autowired
    private LinkyoyoAiConfig linkyoyoAiConfig;

    public void CallOpenAiBySse(String baseString64, SseEmitter sseEmitter) {

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential("REDACTED_AZURE_KEY"))
                .endpoint("https://bluecloud-bca-ai.openai.azure.com/")
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();

        List<ChatRequestMessage> chatMessages = new ArrayList<>();
        String baseString = "";
        if (StrUtil.isNotEmpty(baseString64))
            baseString = String.format("data:image/jpeg;base64,%s", baseString64);

        chatMessages.add(new ChatRequestSystemMessage("You are a helpful assistant. You will talk like a pirate."));

        if (!StrUtil.isEmptyIfStr(baseString))
            chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                    new ChatMessageTextContentItem("分析这张图片，用json格式输出，解析内容:标准编号，标题，发布日期，发布单位"),
                    new ChatMessageImageContentItem(
                            new ChatMessageImageUrl(baseString).setDetail(ChatMessageImageDetailLevel.AUTO))
            )));

        ChatCompletionsOptions chatCompletionsOptions = new ChatCompletionsOptions(chatMessages);
        chatCompletionsOptions.setMaxTokens(2048);
        chatCompletionsOptions.setTemperature(1.0);
        chatCompletionsOptions.setTopP(0.8);

        IterableStream<ChatCompletions> chatCompletionsStream = client.getChatCompletionsStream("gpt-4o-mini",
                chatCompletionsOptions);

        chatCompletionsStream
                .stream()
                .forEach(chatCompletions -> {
                    ChatResponseMessage delta = chatCompletions.getChoices().get(0).getDelta();
                    if (delta.getRole() != null) {
                    }
                    if (delta.getContent() != null) {
                        try {
                            Thread.sleep(100);
                            sseEmitter.send(SseEmitter.event().name("answer").data(delta.getContent()));
                        } catch (Exception e) {
                            log.error("返回错误:{}", e.getMessage());
                        }
                    }
                });
    }

    public List callOpenAi(String baseString64) {

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential("REDACTED_AZURE_KEY"))
                .endpoint("https://bluecloud-bca-ai.openai.azure.com/")
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();

        List<ChatRequestMessage> chatMessages = new ArrayList<>();
        String baseString = "";
        if (StrUtil.isNotEmpty(baseString64))
            baseString = String.format("data:image/jpeg;base64,%s", baseString64);

        chatMessages.add(new ChatRequestSystemMessage("You are a helpful assistant. You will talk like a pirate."));
        if (!StrUtil.isEmptyIfStr(baseString))
            chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                    new ChatMessageTextContentItem("分析这张图片，用json格式输出，解析内容:标准编号，标题，发布日期，发布单位"),
                    new ChatMessageImageContentItem(
                            new ChatMessageImageUrl(baseString).setDetail(ChatMessageImageDetailLevel.AUTO))
            )));

        ChatCompletionsOptions chatCompletionsOptions = new ChatCompletionsOptions(chatMessages);
        chatCompletionsOptions.setMaxTokens(2048);
        chatCompletionsOptions.setTemperature(1.0);
        chatCompletionsOptions.setTopP(0.8);
        ChatCompletions chatCompletions = client.getChatCompletions("gpt-4o-mini", chatCompletionsOptions);

        String returnMessage = "";
        for (ChatChoice choice : chatCompletions.getChoices()) {
            ChatResponseMessage message = choice.getMessage();
            returnMessage = returnMessage + message.getContent();
        }

        log.info("llm解析结果:{}", returnMessage);
        String jsonString = StringParseUtils.getString(returnMessage, "```json\n{\n", "\n}\n```");
        List<String> lst = new ArrayList<>();
        if (StrUtil.isNotEmpty(jsonString)) {
            JSONObject jsonObject = new JSONObject("{" + jsonString + "}");
            if (Objects.nonNull(jsonObject.get("标准编号")))
                lst.add(jsonObject.get("标准编号").toString());
            if (Objects.nonNull(jsonObject.get("标题")))
                lst.add(jsonObject.get("标题").toString());
            if (Objects.nonNull(jsonObject.get("发布日期")))
                lst.add(jsonObject.get("发布日期").toString().concat(" 发布"));
            if (Objects.nonNull(jsonObject.get("发布单位")))
                lst.add(jsonObject.get("发布单位").toString().concat(" 发布"));

            return lst;
        }

        return null;
    }

    public JSONObject callNewOpenAi(String baseString64) {

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential("REDACTED_AZURE_KEY"))
                .endpoint("https://bluecloud-bca-ai.openai.azure.com/")
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();

        List<ChatRequestMessage> chatMessages = new ArrayList<>();
        String baseString = "";
        if (StrUtil.isNotEmpty(baseString64))
            baseString = String.format("data:image/jpeg;base64,%s", baseString64);

        chatMessages.add(new ChatRequestSystemMessage("识别内容：标准级别，标准编号，标题，发布日期，发布单位，以json格式输出。其中标准级别：GB;YC;YQ;DB5305;Q/HNYC;Q/PDSYC;标准编号:需要包含标准级别完整解析。如何没有解析要求的内容，输出{}"));

        if (!StrUtil.isEmptyIfStr(baseString))
            chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                    new ChatMessageTextContentItem("分析"),
                    new ChatMessageImageContentItem(
                            new ChatMessageImageUrl(baseString).setDetail(ChatMessageImageDetailLevel.AUTO))
            )));

        ChatCompletionsOptions chatCompletionsOptions = new ChatCompletionsOptions(chatMessages);
        chatCompletionsOptions.setMaxTokens(2048);
        chatCompletionsOptions.setTemperature(1.0);
        chatCompletionsOptions.setTopP(0.8);
        ChatCompletions chatCompletions = client.getChatCompletions("us-east-gpt4o", chatCompletionsOptions);

        String returnMessage = "";
        for (ChatChoice choice : chatCompletions.getChoices()) {
            ChatResponseMessage message = choice.getMessage();
            returnMessage = returnMessage + message.getContent();
        }

        log.info("llm解析结果:{}", returnMessage);
        String jsonString = StringParseUtils.getString(returnMessage, "{\n", "\n}");

        JSONObject obj = new JSONObject();
        if (StrUtil.isNotEmpty(jsonString)) {
            JSONObject jsonObject = new JSONObject("{" + jsonString + "}");
            if (Objects.nonNull(jsonObject.get("标准级别")))
                obj.putOnce("standardLevelName", jsonObject.get("标准级别").toString());

            if (Objects.nonNull(jsonObject.get("标准编号"))) {
                obj.putOnce("standardNo", jsonObject.get("标准编号").toString().contains(jsonObject.get("标准级别").toString()) ? jsonObject.get("标准编号").toString() :
                        jsonObject.get("标准级别").toString().concat(" ").concat(jsonObject.get("标准编号").toString()));
            }

            if (Objects.nonNull(jsonObject.get("标准编号")) && jsonObject.get("标准编号").toString().startsWith("Q/")
                    && jsonObject.get("标准级别").toString().length() <= 3) {
                obj.set("standardLevelName", "Q/" + StringParseUtils.getString(jsonObject.get("标准编号").toString(), "Q/", "YC") + "YC");
            }

            if (Objects.nonNull(jsonObject.get("标题")))
                obj.putOnce("standardName", jsonObject.get("标题").toString());

            if (Objects.nonNull(jsonObject.get("发布日期")))
                obj.putOnce("publishDate", jsonObject.get("发布日期").toString().toLowerCase().replace("xx", "01"));

            if (Objects.nonNull(jsonObject.get("发布单位")))
                obj.putOnce("publishUnit", jsonObject.get("发布单位").toString());

            return obj;
        }

        return null;
    }

    public JSONObject callAi(File file) {

        JSONObject responseBody = null;

        RequestBody requestBody = new MultipartBody.Builder().setType(MultipartBody.FORM)
                .addFormDataPart("file", file.getName(), RequestBody.create(MediaType.parse("image/png"), file))
                .build();

        String uploadUrl = "https://ai-verify.bluecloudatlas.cn/gateway/hcmsp-ai-keystone/api/files/upload";
        String authToken = "";

        if (linkyoyoAiConfig != null) {
            authToken = linkyoyoAiConfig.getToken();
        }

        Request request = new Request.Builder()
                .url(uploadUrl)
                .header("Authorization", "Bearer " + authToken)
                .post(requestBody)
                .build();
        Response response = null;
        try {
            OkHttpClient okHttpClient = new OkHttpClient();
            response = okHttpClient.newCall(request).execute();
            int status = response.code();
            if (response.isSuccessful()) {
                JSONObject rtnJson = new JSONObject(response.body().string());
                String fileId = rtnJson.get("id").toString();
                requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"),
                        String.format("{" +
                                "    \n" +
                                "    \"response_mode\": \"blocking\",\n" +
                                "    \"inputs\": {},\n" +
                                "    \"query\": \"分析图片中内容\",\n" +
                                "    \"files\": [\n" +
                                "        {\n" +
                                "            \"transfer_method\": \"local_file\",\n" +
                                "            \"type\": \"image\",\n" +
                                "            \"upload_file_id\": \"%s\",\n" +
                                "            \"url\": \"\"\n" +
                                "        }\n" +
                                "    ],\n" +
                                "    \"custom_files\": [],\n" +
                                "    \"open_internet\": false\n" +
                                "}", fileId));

                String chatUrl = "https://ai-verify.bluecloudatlas.cn/gateway/hcmsp-ai-keystone/api/chat-messages";

                if (linkyoyoAiConfig != null) {
                    chatUrl = linkyoyoAiConfig.getUrl();
                }

                request = new Request.Builder()
                        .url(chatUrl)
                        .header("Authorization", "Bearer " + authToken)
                        .post(requestBody)
                        .build();

                response = okHttpClient.newCall(request).execute();
                if (response.isSuccessful()) {
                    rtnJson = new JSONObject(response.body().string());
                    String content = rtnJson.getJSONObject("data").get("answer").toString();

                    String jsonString = StringParseUtils.getString(content, "```json\n{\n", "\n}\n```");
                    log.info("ai 解析内容：{}", jsonString);
                    JSONObject obj = new JSONObject();
                    if (StrUtil.isNotEmpty(jsonString)) {
                        JSONObject jsonObject = new JSONObject("{" + jsonString + "}");
                        if (Objects.nonNull(jsonObject.get("标准级别")))
                            obj.putOnce("standardLevelName", jsonObject.get("标准级别").toString());

                        if (Objects.nonNull(jsonObject.get("标准号"))) {
                            obj.putOnce("standardNo", jsonObject.get("标准号").toString().contains(jsonObject.get("标准级别").toString()) ? jsonObject.get("标准号").toString() :
                                    jsonObject.get("标准级别").toString().concat(" ").concat(jsonObject.get("标准号").toString()));
                        }

                        if (Objects.nonNull(jsonObject.get("标准号")) && jsonObject.get("标准号").toString().startsWith("Q/")
                                && jsonObject.get("标准级别").toString().length() <= 3) {
                            obj.set("standardLevelName", "Q/" + StringParseUtils.getString(jsonObject.get("标准号").toString(), "Q/", "YC") + "YC");
                        }

                        if (Objects.nonNull(jsonObject.get("标准名称")))
                            obj.putOnce("standardName", jsonObject.get("标准名称").toString());

                        if (Objects.nonNull(jsonObject.get("标准发布日期")))
                            obj.putOnce("publishDate", jsonObject.get("标准发布日期").toString().toLowerCase().replace("xx", "01"));

                        if (Objects.nonNull(jsonObject.get("标准发布单位")))
                            obj.putOnce("publishUnit", jsonObject.get("标准发布单位").toString());

                        return obj;
                    }
                }
            }
        } catch (Exception e) {
            log.error("okhttp3 post error >> ex = {}", e.getMessage());
        } finally {
            if (response != null) {
            }
        }

        return null;
    }

    public JSONObject callAiWithOkHttp(String content) {
        if (aiConfig == null) {
            log.error("AiConfig未注入，使用默认配置");
            return callAiWithOkHttp(content, true, "https://subs1-5.openai.azure.com/",
                    "REDACTED_AZURE_OPENAI_KEY_2",
                    "gpt-4o-5", "2024-05-01-preview",
                    "解析内容：标准类型（国标   ||   行业标准 ||  企业标准/地方标准）,标准号,标准中文名,标准英文名，发布日期,实施日期,标准状态,发布单位,提出单位,起草单位,起草人,范围,规范性引用文件,**前言,引言,术语和定义,参考文献**;以json格式输出");
        }
        return callAiWithOkHttp(content, aiConfig.isAzure(), aiConfig.getUrl(), aiConfig.getKey(),
                aiConfig.getModel(), aiConfig.getVersion(), aiConfig.getPrompt());
    }

    public JSONObject callDeepSeekAi(String content) {
        if (aiConfig == null) {
            log.error("AiConfig未注入，使用默认配置");
            return callAiWithOkHttp(content, false, "https://api.deepseek.com/v1/chat/completions",
                    "REDACTED_DEEPSEEK_API_KEY", "deepseek-chat", "",
                    "解析内容：标准类型（国标   ||   行业标准 ||  企业标准/地方标准）,标准号,标准中文名,标准英文名，发布日期,实施日期,标准状态,发布单位,提出单位,起草单位,起草人,范围,规范性引用文件,**前言,引言,术语和定义,参考文献**;以json格式输出");
        }
        return callAiWithOkHttp(content, aiConfig.isDeepseekIsAzure(), aiConfig.getDeepseekUrl(),
                aiConfig.getDeepseekKey(), aiConfig.getDeepseekModel(), "", aiConfig.getDeepseekPrompt());
    }

    private OkHttpClient createSecureHttpClient() throws Exception {
        final TrustManager[] trustAllCerts = new TrustManager[]{
                new X509TrustManager() {
                    @Override
                    public void checkClientTrusted(java.security.cert.X509Certificate[] chain, String authType) {
                    }

                    @Override
                    public void checkServerTrusted(java.security.cert.X509Certificate[] chain, String authType) {
                    }

                    @Override
                    public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                        return new java.security.cert.X509Certificate[]{};
                    }
                }
        };

        final SSLContext sslContext = SSLContext.getInstance("SSL");
        sslContext.init(null, trustAllCerts, new java.security.SecureRandom());

        return new OkHttpClient.Builder()
                .sslSocketFactory(sslContext.getSocketFactory(), (X509TrustManager) trustAllCerts[0])
                .hostnameVerifier((hostname, session) -> true)
                .connectTimeout(60, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .build();
    }

    private JSONObject buildRequestJson(String promptMarkDown, String content, String model, boolean isAzure) {
        JSONObject jsonRequest = new JSONObject();
        jsonRequest.set("temperature", 0.1);
        jsonRequest.set("max_tokens", 8000);

        if (!isAzure) {
            jsonRequest.set("model", model);
        }

        JSONObject systemMessage = new JSONObject();
        systemMessage.set("role", "system");
        systemMessage.set("content", "You are a helpful assistant.");

        JSONObject userMessage = new JSONObject();
        userMessage.set("role", "user");
        userMessage.set("content", promptMarkDown + "\n" + content);

        jsonRequest.set("messages", new JSONObject[]{systemMessage, userMessage});

        return jsonRequest;
    }

    private JSONObject extractAndParseContent(JSONObject jsonResponse) {
        String content_text = jsonResponse.getJSONArray("choices")
                .getJSONObject(0)
                .getJSONObject("message")
                .getStr("content");

        try {
            String jsonString = StringParseUtils.substringBetween(content_text, "\n{", "}\n");
            log.info("AI解析内容：{}", jsonString);

            if (StrUtil.isEmpty(jsonString)) {
                return null;
            }

            return JSONUtil.parseObj("{" + jsonString + "}");
        } catch (Exception e) {
            log.error("解析AI响应内容为JSON失败: {}", e.getMessage());
            JSONObject result = new JSONObject();
            result.set("content", content_text);
            return result;
        }
    }

    public JSONObject callAiWithOkHttp(String content, boolean isAzure, String url, String key,
                                       String model, String version, String promptMarkDown) {
        try {
            OkHttpClient client = createSecureHttpClient();
            log.info("创建OkHttpClient并设置超时: 连接超时=60秒, 读取超时=120秒, 写入超时=60秒");

            String endpoint;
            if (isAzure) {
                if (!url.endsWith("/")) {
                    url = url + "/";
                }
                endpoint = url + "openai/deployments/" + model + "/chat/completions?api-version=" + version;
                log.info("请求Azure OpenAI端点: {}", endpoint);
            } else {
                endpoint = url;
                log.info("请求DeepSeek端点: {}", endpoint);
                log.info("使用模型: {}", model);
            }

            JSONObject jsonRequest = buildRequestJson(promptMarkDown, content, model, isAzure);
            String jsonBody = jsonRequest.toString();
            RequestBody requestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);

            Request.Builder requestBuilder = new Request.Builder()
                    .url(endpoint)
                    .addHeader("Content-Type", "application/json")
                    .post(requestBody);

            if (isAzure) {
                requestBuilder.addHeader("api-key", key);
            } else {
                requestBuilder.addHeader("Authorization", "Bearer " + key);
                log.info("请求头信息: Authorization=Bearer {}, Content-Type={}", key, "application/json");
            }

            Request request = requestBuilder.build();

            Response response = client.newCall(request).execute();

            if (response.isSuccessful()) {
                String responseBody = response.body().string();
                log.info("AI响应: {}", responseBody);

                JSONObject jsonResponse = JSONUtil.parseObj(responseBody);

                return extractAndParseContent(jsonResponse);
            } else {
                String errorBody = "";
                try {
                    errorBody = response.body().string();
                    log.error("AI请求失败详情: {}", errorBody);
                } catch (Exception e) {
                    log.error("无法读取错误响应体: {}", e.getMessage());
                }

                log.error("AI请求失败: {} - {}", response.code(), response.message());
                log.error("请求URL: {}", request.url());
                log.error("请求头: {}", request.headers());

                JSONObject errorResult = new JSONObject();
                errorResult.set("error", "请求失败: " + response.code() + " - " + response.message());
                errorResult.set("errorDetails", errorBody);
                return errorResult;
            }

        } catch (Exception e) {
            log.error("调用AI服务异常: {}", e.getMessage(), e);
            JSONObject errorResult = new JSONObject();
            errorResult.set("error", "调用AI服务异常: " + e.getMessage());
            return errorResult;
        }
    }

    public JSONObject callAi(String query) {

        OkHttpClient okHttpClient = new OkHttpClient().newBuilder()
                .connectTimeout(1, TimeUnit.MINUTES)
                .readTimeout(1, TimeUnit.MINUTES)
                .writeTimeout(1, TimeUnit.MINUTES)
                .build();
        String orgQuery = query;
        try {
            JSONObject modelCompletionParams = new JSONObject();
            modelCompletionParams.set("frequency_penalty", 0);
            modelCompletionParams.set("max_tokens", 4096);
            modelCompletionParams.set("presence_penalty", 0);
            modelCompletionParams.set("stop", new String[]{});
            modelCompletionParams.set("temperature", 0);
            modelCompletionParams.set("top_p", 1);

            JSONObject modelConfig = new JSONObject();
            modelConfig.set("completion_params", modelCompletionParams);
            modelConfig.set("is_system", true);
            modelConfig.set("mode", "chat");
            modelConfig.set("name", "gpt-4o-5");
            modelConfig.set("provider", "azure_openai");
            modelConfig.set("vision", true);

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

            JSONObject requestJson = new JSONObject();
            requestJson.set("model_config", new JSONObject()
                    .set("annotation_reply", new JSONObject().set("enabled", false))
                    .set("file_upload", fileUploadConfig)
                    .set("index_enhance_config", null)
                    .set("model", modelConfig)
                    .set("more_like_this", new JSONObject().set("enabled", false))
                    .set("opening_statement", "")
                    .set("retriever_resource", new JSONObject().set("enabled", false))
                    .set("sensitive_word_avoidance", new JSONObject().set("enabled", false))
                    .set("speech_to_text", new JSONObject().set("enabled", false))
                    .set("suggested_questions", new String[]{})
                    .set("suggested_questions_after_answer", new JSONObject().set("enabled", false))
                    .set("system_parameters", systemParameters)
                    .set("text_to_speech", textToSpeech)
                    .set("url_format", null)
                    .set("user_input_form", new String[]{})
                    .set("userAppConfig", userAppConfig)
            );
            requestJson.set("response_mode", "blocking");
            requestJson.set("inputs", new JSONObject());
            requestJson.set("query", query);
            requestJson.set("conversation_id", "");
            requestJson.set("files", new String[]{});
            requestJson.set("custom_files", new String[]{});
            requestJson.set("file_read_info", null);
            requestJson.set("open_internet", false);

            String requestContent = requestJson.toString();
            RequestBody requestBody = RequestBody.create(MediaType.parse("application/json; charset=utf-8"), requestContent);

            Request request = new Request.Builder()
                    .url(linkyoyoAiConfig.getUrl())
                    .header("Authorization", "Bearer " + linkyoyoAiConfig.getToken())
                    .post(requestBody)
                    .build();
            Response response = null;
            try {
                response = okHttpClient.newCall(request).execute();
            } catch (Exception e) {
                log.error("blue ai 解析 error:{},query:{}", e.getMessage(), orgQuery);
                return null;
            }
            if (response.isSuccessful()) {
                JSONObject rtnJson = new JSONObject(response.body().string());
                String content = rtnJson.getJSONObject("data").get("answer").toString();

                String jsonString = StringParseUtils.substringBetween(content, "\n{", "}\n");
                log.info("AI解析内容：{}", jsonString);

                if (StrUtil.isEmpty(jsonString)) {
                    return null;
                }

                return JSONUtil.parseObj("{" + jsonString + "}");
            }

        } catch (Exception e) {
            log.error("okhttp3 post error >> ex = {}", e.getMessage());
        } finally {
        }

        return null;
    }
}
