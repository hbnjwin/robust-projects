package com.linkyoyo.reportaudit.service;

import java.util.Map;

public interface AiService {

    /**
     * 调用Azure OpenAI服务解析内容
     * @param content 需要解析的内容
     * @return 解析结果
     */
    Map<String, Object> callAzureAi(String content);

    /**
     * 调用DeepSeek AI服务解析内容
     * @param content 需要解析的内容
     * @return 解析结果
     */
    Map<String, Object> callDeepSeekAi(String content);

    /**
     * 解析Markdown内容，根据参数选择AI服务
     * @param fileBytes 文件字节内容
     * @param originalFilename 原始文件名
     * @param useDeepSeek 是否使用DeepSeek AI
     * @return 解析结果
     */
    Map<String, Object> analyzeMarkdown(byte[] fileBytes, String originalFilename, boolean useDeepSeek);

    /**
     * 使用callAi方法解析Markdown内容
     * @param fileBytes 文件字节内容
     * @param originalFilename 原始文件名
     * @return 解析结果
     */
    Map<String, Object> analyzeMarkdownWithCallAi(byte[] fileBytes, String originalFilename);
}
