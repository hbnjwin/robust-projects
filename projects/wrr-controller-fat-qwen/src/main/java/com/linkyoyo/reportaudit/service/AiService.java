package com.linkyoyo.reportaudit.service;

import java.util.Map;

public interface AiService {

    /**
     * 调用Azure OpenAI服务解析内容
     *
     * @param content 需要解析的内容（原始内容，Service内部会进行特殊字符处理）
     * @return AI解析结果
     * @throws RuntimeException 当AI调用返回error时抛出，message为error描述
     */
    Map<String, Object> callAzureAi(String content);

    /**
     * 调用DeepSeek AI服务解析内容
     *
     * @param content 需要解析的内容（原始内容，Service内部会进行特殊字符处理）
     * @return AI解析结果
     * @throws RuntimeException 当AI调用返回error时抛出，message为error描述
     */
    Map<String, Object> callDeepSeekAi(String content);

    /**
     * 上传Markdown文件并使用AI解析
     *
     * @param markdownContent Markdown文件内容
     * @param originalFilename 原始文件名
     * @param useDeepSeek 是否使用DeepSeek AI（false时使用Azure）
     * @return AI解析结果（包含originalFilename字段）
     * @throws RuntimeException 当AI调用返回error时抛出，message为error描述
     */
    Map<String, Object> uploadAndAnalyzeMd(String markdownContent, String originalFilename, boolean useDeepSeek);

    /**
     * 上传MD文件并调用callAi方法解析内容
     *
     * @param markdownContent MD文件内容
     * @param originalFilename 原始文件名
     * @return AI解析结果（包含originalFilename字段）
     * @throws RuntimeException 当AI返回null或调用失败时抛出
     */
    Map<String, Object> uploadMdToCallAi(String markdownContent, String originalFilename);
}
