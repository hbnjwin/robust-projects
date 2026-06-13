package com.linkyoyo.reportaudit.util.llm;

import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONObject;

/**
 * Linkyoyo Agent请求体构建器
 * 统一CommonFunc.callAi(String)和DynamicLLMService.buildLinkyoyoAgentRequest中的重复逻辑
 */
public final class LinkyoyoRequestBuilder {

    private LinkyoyoRequestBuilder() {
    }

    /**
     * 构建Linkyoyo Agent文本聊天请求体
     *
     * @param query       用户查询文本
     * @param modelName   模型名称（如 "gpt-4o-5"）
     * @param temperature 温度参数（0.0 - 2.0）
     * @param maxTokens   最大返回token数
     * @return 完整的请求JSONObject
     */
    public static JSONObject buildRequest(String query, String modelName,
                                          float temperature, int maxTokens) {
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
        modelConfig.set("name", modelName);
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

    /**
     * 构建Linkyoyo Agent文件聊天请求体
     * 用于CommonFunc.callAi(File)中的两步上传流程
     *
     * @param fileId 上传文件后返回的文件ID
     * @return 请求JSONObject
     */
    public static JSONObject buildFileChatRequest(String fileId) {
        JSONObject fileObj = new JSONObject();
        fileObj.set("transfer_method", "local_file");
        fileObj.set("type", "image");
        fileObj.set("upload_file_id", fileId);
        fileObj.set("url", "");

        JSONArray filesArray = new JSONArray();
        filesArray.add(fileObj);

        JSONObject requestJson = new JSONObject();
        requestJson.set("response_mode", "blocking");
        requestJson.set("inputs", new JSONObject());
        requestJson.set("query", "分析图片中内容");
        requestJson.set("files", filesArray);
        requestJson.set("custom_files", new String[]{});
        requestJson.set("open_internet", false);

        return requestJson;
    }
}
