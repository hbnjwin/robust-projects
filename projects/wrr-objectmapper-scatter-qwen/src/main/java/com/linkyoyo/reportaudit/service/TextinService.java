package com.linkyoyo.reportaudit.service;

/**
 * TextinService - 处理PDF到Markdown的转换
 *
 * 注意：TextIn API的响应格式已更新，包含以下字段：
 * 响应格式示例：
 * {
 *   "duration": 3259,
 *   "message": "Success",
 *   "result": {
 *     "markdown": "...markdown content...",
 *     "success_count": 14,
 *     "pages": [...]
 *   }
 * }
 *
 * 已添加@JsonIgnoreProperties注解以忽略未知字段，提高代码对API变化的适应性。
 */

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.config.BlueCloudAiConfig;
import com.linkyoyo.reportaudit.config.TextinConfig;
import com.linkyoyo.reportaudit.dto.BlueCloudAiMarkdownResponse;
import com.linkyoyo.reportaudit.dto.BlueCloudAiResponse;
import com.linkyoyo.reportaudit.dto.TextinResponse;
import com.linkyoyo.reportaudit.entity.SysParaset;
import com.linkyoyo.reportaudit.model.ConversionTask;
import com.linkyoyo.reportaudit.model.Document;
import com.linkyoyo.reportaudit.repository.ConversionTaskRepository;
import com.linkyoyo.reportaudit.repository.DocumentRepository;
import com.linkyoyo.reportaudit.repository.SysParasetRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
@RequiredArgsConstructor
public class TextinService {

    @Value("${paraSet.standardDocPath}")
    private String standardDocPath;
    
    @Value("${paraSet.uploadPath:d:/data/upload}")
    private String uploadPath;

    private final TextinConfig textinConfig;
    private final BlueCloudAiConfig blueCloudAiConfig;
    private final DocumentRepository documentRepository;
    private final ConversionTaskRepository conversionTaskRepository;
    private final OkHttpClient okHttpClient = new OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .build();
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @Autowired
    private SysParasetRepository sysParasetRepository;

    /**
     * 将Markdown内容保存到指定路径下的MD文件
     *
     * @param markdown Markdown内容
     * @param fileName 文件名（不包含路径和扩展名）
     * @param customPath 自定义保存路径，如果为null则使用默认路径
     */
    private void saveMarkdownToFile(String markdown, String fileName, String customPath) {
        try {
            // 确定保存路径
            String savePath = customPath != null ? customPath : standardDocPath;

            // 创建目录（如果不存在）
            Path docDir = Paths.get(savePath);
            if (!Files.exists(docDir)) {
                Files.createDirectories(docDir);
            }

            // 处理文件名，去除可能的路径和扩展名
            String baseName = new File(fileName).getName();
            if (baseName.contains(".")) {
                baseName = baseName.substring(0, baseName.lastIndexOf('.'));
            }

            // 创建MD文件路径
            String mdFilePath = savePath + File.separator + baseName + ".md";

            // 将Markdown内容写入文件
            try (FileWriter writer = new FileWriter(mdFilePath)) {
                writer.write(markdown);
            }

            log.info("已将Markdown内容保存到文件: {}", mdFilePath);
        } catch (IOException e) {
            log.error("保存Markdown内容到文件时出错", e);
        }
    }

    /**
     * 将Markdown内容保存到标准文档路径下的MD文件
     *
     * @param markdown Markdown内容
     * @param fileName 文件名（不包含路径和扩展名）
     */
    private void saveMarkdownToFile(String markdown, String fileName) {
        saveMarkdownToFile(markdown, fileName, null);
    }

    /**
     * 将JSON响应内容保存到标准文档路径下的JSON文件
     *
     * @param jsonContent JSON响应内容
     * @param fileName 文件名（不包含路径和扩展名）
     */
    private void saveJsonResponseToFile(String jsonContent, String fileName) {
        try {
            // 创建标准文档目录（如果不存在）
            Path docDir = Paths.get(standardDocPath);
            if (!Files.exists(docDir)) {
                Files.createDirectories(docDir);
            }

            // 处理文件名，去除可能的路径和扩展名
            String baseName = new File(fileName).getName();
            if (baseName.contains(".")) {
                baseName = baseName.substring(0, baseName.lastIndexOf('.'));
            }

            // 创建JSON文件路径
            String jsonFilePath = standardDocPath + File.separator + baseName + ".json";

            // 将JSON响应内容写入文件
            try (FileWriter writer = new FileWriter(jsonFilePath)) {
                writer.write(jsonContent);
            }

            log.info("已将JSON响应内容保存到文件: {}", jsonFilePath);
        } catch (IOException e) {
            log.error("保存JSON响应内容到文件时出错", e);
        }
    }

    /**
     * 创建一个PDF转Markdown的转换任务
     *
     * @param fileName 文件名
     * @return 转换任务
     */
    public ConversionTask createConversionTask(String fileName) {
        return conversionTaskRepository.create(fileName);
    }

    /**
     * 创建一个PDF转Markdown的转换任务
     *
     * @param file PDF文件
     * @return 转换任务
     */
    public ConversionTask createConversionTask(MultipartFile file) {
        return conversionTaskRepository.create(file.getOriginalFilename());
    }

    /**
     * 获取转换任务状态
     *
     * @param taskId 任务ID
     * @return 转换任务
     */
    public ConversionTask getConversionTask(String taskId) {
        return conversionTaskRepository.findById(taskId);
    }

    /**
     * 异步转换PDF到Markdown（二进制文件上传）
     *
     * @param file PDF文件
     * @param taskId 任务ID
     */
    @Async
    public CompletableFuture<String> convertPdfToMarkdownAsync(MultipartFile file, String taskId) {
        try {
            // 更新任务状态为处理中
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            // 获取文件字节数组
            byte[] fileBytes = file.getBytes();
            String contentType = file.getContentType();

            // 创建请求体（使用原始二进制数据）
            RequestBody requestBody = RequestBody.create(MediaType.parse("application/octet-stream"), fileBytes);

            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 30);

            // 创建请求头
            Request request = new Request.Builder()
                    .url(textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown?image_output_type=base64str")
                    .addHeader("x-ti-app-id", textinConfig.getAppId())
                    .addHeader("x-ti-secret-code", textinConfig.getSecretCode())
                    .post(requestBody)
                    .build();

            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 50);

            // 执行请求
            try (Response response = okHttpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    log.error("Error converting PDF to Markdown: {}", response);
                    conversionTaskRepository.fail(taskId, "Failed to convert PDF to Markdown: " + response.code());
                    return CompletableFuture.completedFuture(null);
                }

                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 70);

                // 解析响应
                String responseBody = response.body().string();
                log.info("Textin API response: {}", responseBody);

                // 将JSON响应内容保存到文件
                saveJsonResponseToFile(responseBody, file.getOriginalFilename());

                // 使用JsonNode解析JSON
                JsonNode rootNode = objectMapper.readTree(responseBody);

                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

                // 提取result->markdown内容
                if (rootNode.has("result") && rootNode.get("result").has("markdown")) {
                    String markdown = rootNode.get("result").get("markdown").asText();

                    // 存储文档
                    Document document = documentRepository.save(
                            file.getOriginalFilename(),
                            null, // Text field is no longer available in the API response
                            markdown
                    );

                    // 同时将Markdown内容保存到/doc目录下的MD文件
                    saveMarkdownToFile(markdown, file.getOriginalFilename());

                    // 更新任务状态为完成
                    conversionTaskRepository.complete(taskId, document.getId());
                    return CompletableFuture.completedFuture(document.getId());
                } else {
                    conversionTaskRepository.fail(taskId, "Failed to convert PDF to Markdown: No markdown content");
                    return CompletableFuture.completedFuture(null);
                }
            }
        } catch (Exception e) {
            log.error("Error converting PDF to Markdown", e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        }
    }

    /**
     * 异步通过URL转换文件到Markdown
     *
     * @param fileUrl 文件URL
     * @param fileName 文件名（可选）
     * @param taskId 任务ID
     */
    @Async
    public CompletableFuture<String> convertUrlToMarkdownAsync(String fileUrl, String fileName, String taskId) {
        try {
            // 更新任务状态为处理中
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            // 创建请求体（纯文本，包含URL）
            RequestBody requestBody = RequestBody.create(MediaType.parse("text/plain"), fileUrl);

            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 30);

            // 创建请求头
            Request request = new Request.Builder()
                    .url(textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown?image_output_type=base64str")
                    .addHeader("x-ti-app-id", textinConfig.getAppId())
                    .addHeader("x-ti-secret-code", textinConfig.getSecretCode())
                    .post(requestBody)
                    .build();

            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 50);

            // 执行请求
            try (Response response = okHttpClient.newCall(request).execute()) {
                if (!response.isSuccessful()) {
                    log.error("Error converting URL to Markdown: {}", response);
                    conversionTaskRepository.fail(taskId, "Failed to convert URL to Markdown: " + response.code());
                    return CompletableFuture.completedFuture(null);
                }

                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 70);

                // 解析响应
                String responseBody = response.body().string();
                log.info("Textin API response: {}", responseBody);

                // 将JSON响应内容保存到文件
                String jsonFileName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
                saveJsonResponseToFile(responseBody, jsonFileName);

                // 使用JsonNode解析JSON
                JsonNode rootNode = objectMapper.readTree(responseBody);

                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

                // 提取result->markdown内容
                if (rootNode.has("result") && rootNode.get("result").has("markdown")) {
                    String markdown = rootNode.get("result").get("markdown").asText();

                    // 存储文档
                    String docName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
                    Document document = documentRepository.save(
                            docName,
                            null, // Text field is no longer available in the API response
                            markdown
                    );

                    // 同时将Markdown内容保存到/doc目录下的MD文件
                    saveMarkdownToFile(markdown, docName);

                    // 更新任务状态为完成
                    conversionTaskRepository.complete(taskId, document.getId());
                    return CompletableFuture.completedFuture(document.getId());
                } else {
                    conversionTaskRepository.fail(taskId, "Failed to convert URL to Markdown: No markdown content");
                    return CompletableFuture.completedFuture(null);
                }
            }
        } catch (Exception e) {
            log.error("Error converting URL to Markdown", e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        }
    }

    /**
     * 同步转换PDF到Markdown（二进制文件上传）
     *
     * @param file PDF文件
     * @return TextinResponse 包含转换结果
     * @throws IOException 如果转换过程中发生错误
     */
    public TextinResponse convertPdfToMarkdown(MultipartFile file) throws IOException {
        // 获取文件字节数组
        byte[] fileBytes = file.getBytes();
        String contentType = file.getContentType();

        // 创建请求体（使用原始二进制数据）
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/octet-stream"), fileBytes);

        // 创建请求头
        Request request = new Request.Builder()
                .url(textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown?image_output_type=base64str&get_image=objects")
                .addHeader("x-ti-app-id", textinConfig.getAppId())
                .addHeader("x-ti-secret-code", textinConfig.getSecretCode())
                .post(requestBody)
                .build();

        // 执行请求
        try (Response response = okHttpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                log.error("Error converting PDF to Markdown: {}", response);
                throw new IOException("Failed to convert PDF to Markdown: " + response.code());
            }

            // 解析响应
            String responseBody = response.body().string();
            log.info("Textin API response: {}", responseBody);

            // 将JSON响应内容保存到文件
            saveJsonResponseToFile(responseBody, file.getOriginalFilename());

            // 使用JsonNode解析JSON
            JsonNode rootNode = objectMapper.readTree(responseBody);

            // 创建TextinResponse对象
            TextinResponse textinResponse = new TextinResponse();
            if (rootNode.has("duration")) {
                textinResponse.setDuration(rootNode.get("duration").asInt());
            }
            if (rootNode.has("message")) {
                textinResponse.setMessage(rootNode.get("message").asText());
            }

            // 提取result->markdown内容
            if (rootNode.has("result")) {
                JsonNode resultNode = rootNode.get("result");
                TextinResponse.TextinResult result = new TextinResponse.TextinResult();

                if (resultNode.has("markdown")) {
                    String markdown = resultNode.get("markdown").asText();
                    result.setMarkdown(markdown);

                    // 存储文档
                    documentRepository.save(
                            file.getOriginalFilename(),
                            null, // Text field is no longer available in the API response
                            markdown
                    );

                    // 同时将Markdown内容保存到/doc目录下的MD文件
                    saveMarkdownToFile(markdown, file.getOriginalFilename());
                }

                if (resultNode.has("success_count")) {
                    result.setSuccess_count(resultNode.get("success_count").asInt());
                }

                if (resultNode.has("pages")) {
                    result.setPages(resultNode.get("pages").asInt());
                }

                textinResponse.setResult(result);
            }

            return textinResponse;
        }
    }

    /**
     * 通过URL转换文件到Markdown
     *
     * @param fileUrl 文件URL
     * @param fileName 文件名（可选）
     * @return TextinResponse 包含转换结果
     * @throws IOException 如果转换过程中发生错误
     */
    public TextinResponse convertUrlToMarkdown(String fileUrl, String fileName) throws IOException {
        // 创建请求体（纯文本，包含URL）
        RequestBody requestBody = RequestBody.create(MediaType.parse("text/plain"), fileUrl);

        // 创建请求头
        Request request = new Request.Builder()
                .url(textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown")
                .addHeader("x-ti-app-id", textinConfig.getAppId())
                .addHeader("x-ti-secret-code", textinConfig.getSecretCode())
                .post(requestBody)
                .build();

        // 执行请求
        try (Response response = okHttpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                log.error("Error converting URL to Markdown: {}", response);
                throw new IOException("Failed to convert URL to Markdown: " + response.code());
            }

            // 解析响应
            String responseBody = response.body().string();
            log.info("Textin API response: {}", responseBody);

            // 将JSON响应内容保存到文件
            String jsonFileName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
            saveJsonResponseToFile(responseBody, jsonFileName);

            // 使用JsonNode解析JSON
            JsonNode rootNode = objectMapper.readTree(responseBody);

            // 创建TextinResponse对象
            TextinResponse textinResponse = new TextinResponse();
            if (rootNode.has("duration")) {
                textinResponse.setDuration(rootNode.get("duration").asInt());
            }
            if (rootNode.has("message")) {
                textinResponse.setMessage(rootNode.get("message").asText());
            }

            // 提取result->markdown内容
            if (rootNode.has("result")) {
                JsonNode resultNode = rootNode.get("result");
                TextinResponse.TextinResult result = new TextinResponse.TextinResult();

                if (resultNode.has("markdown")) {
                    String markdown = resultNode.get("markdown").asText();
                    result.setMarkdown(markdown);

                    // 存储文档
                    String docName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
                    documentRepository.save(
                            docName,
                            null, // Text field is no longer available in the API response
                            markdown
                    );

                    // 同时将Markdown内容保存到/doc目录下的MD文件
                    saveMarkdownToFile(markdown, docName);
                }

                if (resultNode.has("success_count")) {
                    result.setSuccess_count(resultNode.get("success_count").asInt());
                }

                if (resultNode.has("pages")) {
                    result.setPages(resultNode.get("pages").asInt());
                }

                textinResponse.setResult(result);
            }

            return textinResponse;
        }
    }

    /**
     * 使用Blue Cloud AI上传PDF文件并转换为Markdown
     *
     * @param file PDF文件
     * @return 包含文档ID的响应
     * @throws IOException 如果转换过程中发生错误
     */
    public String uploadByBlueCloudAi(MultipartFile file) throws IOException {
        return uploadByBlueCloudAiInternal(file.getBytes(), file.getOriginalFilename(), file.getContentType(), null);
    }

    /**
     * 使用Blue Cloud AI上传PDF文件并转换为Markdown（接受File参数）
     *
     * @param file PDF文件
     * @return 包含文档ID的响应
     * @throws IOException 如果转换过程中发生错误
     */
    public String uploadByBlueCloudAi(File file) throws IOException {
        byte[] fileBytes = Files.readAllBytes(file.toPath());
        String fileName = file.getName();
        String contentType = "application/pdf"; // 默认为PDF类型
        String filePath = file.getParent(); // 获取文件所在目录

        return uploadByBlueCloudAiInternal(fileBytes, fileName, contentType, filePath);
    }

    /**
     * 内部方法：使用Blue Cloud AI上传PDF文件并转换为Markdown
     *
     * @param fileBytes 文件字节数组
     * @param fileName 文件名
     * @param contentType 内容类型
     * @param customPath 自定义保存路径，如果为null则使用默认路径
     * @return 包含文档ID的响应
     * @throws IOException 如果转换过程中发生错误
     */
    private String uploadByBlueCloudAiInternal(byte[] fileBytes, String fileName, String contentType, String customPath) throws IOException {
        log.info("开始使用Blue Cloud AI上传文件: {}", fileName);

        // 记录开始时间
        long startTime = System.currentTimeMillis();

        try {
            // 第一步：上传文件到Blue Cloud AI
            // 创建multipart请求体
            RequestBody requestBody = new MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", fileName,
                            RequestBody.create(MediaType.parse(contentType), fileBytes))
                    .build();

            // 创建请求头
            Request uploadRequest = new Request.Builder()
                    .url(blueCloudAiConfig.getUploadApiUrl())
                    .addHeader("Authorization", blueCloudAiConfig.getAuthToken())
                    .post(requestBody)
                    .build();

            // 执行上传请求
            try (Response uploadResponse = okHttpClient.newCall(uploadRequest).execute()) {
                if (!uploadResponse.isSuccessful()) {
                    log.error("Error uploading file to Blue Cloud AI: {}", uploadResponse);
                    throw new IOException("Failed to upload file to Blue Cloud AI: " + uploadResponse.code());
                }

                // 解析上传响应
                String uploadResponseBody = uploadResponse.body().string();
                log.info("Blue Cloud AI upload response: {}", uploadResponseBody);

                // 解析上传响应获取文件ID
                BlueCloudAiResponse uploadResult = objectMapper.readValue(uploadResponseBody, BlueCloudAiResponse.class);
                String fileId = uploadResult.getId();
                log.info("文件上传成功，获取到文件ID: {}", fileId);

                log.info("ai phrase model:{}",blueCloudAiConfig.getProviderName());
                // 第二步：请求转换为Markdown
                // 创建JSON请求体    completion_params  《-model_parameters  model -》name
                String jsonBody = String.format("{"
                        + "\"file_id\": \"%s\","
                        + "\"process_figures\": false,"
                        + "\"provider_name\":\"%s\","
                        + "\"img_model\": {"
                        + "\"provider\": \"%s\","
                        + "\"name\": \"%s\","
                        + "\"is_system\": true,"
                        + "\"completion_params\": {"
                        + "\"temperature\": %s"
                        + "},"
                        + "\"query\": \"%s\""
                        + "}"
                        + "}", fileId, blueCloudAiConfig.getProviderName(), "azure_openai",
                        blueCloudAiConfig.getModelName(), blueCloudAiConfig.getTemperature(), blueCloudAiConfig.getQuery());

                RequestBody markdownRequestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);

                // 创建请求头
                Request markdownRequest = new Request.Builder()
                        .url(blueCloudAiConfig.getMarkdownApiUrl())
                        .addHeader("Authorization", blueCloudAiConfig.getAuthToken())
                        .post(markdownRequestBody)
                        .build();

                // 创建带有超时设置的OkHttpClient
                OkHttpClient clientWithTimeout = okHttpClient.newBuilder()
                        .connectTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(120, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .build();

                // 执行Markdown转换请求
                try (Response markdownResponse = clientWithTimeout.newCall(markdownRequest).execute()) {
                    if (!markdownResponse.isSuccessful()) {
                        log.error("Error converting file to Markdown with Blue Cloud AI: {}", markdownResponse);
                        throw new IOException("Failed to convert file to Markdown with Blue Cloud AI: " + markdownResponse.code());
                    }

                    // 解析Markdown响应
                    String markdownResponseBody = markdownResponse.body().string();
                    log.info("Blue Cloud AI markdown response: {}", markdownResponseBody);

                    // 解析Markdown响应获取内容
                    BlueCloudAiMarkdownResponse markdownResult = objectMapper.readValue(markdownResponseBody, BlueCloudAiMarkdownResponse.class);

                    if (markdownResult.getCode() == 0 && markdownResult.getData() != null) {
                        String markdown = markdownResult.getData().getMarkdown_content();

                        // 存储文档
                        Document document = documentRepository.save(
                                fileName,
                                null,
                                markdown
                        );

                        // 同时将Markdown内容保存到指定目录下的MD文件
                        saveMarkdownToFile(markdown, fileName, customPath);

                        return document.getId();
                    } else {
                        throw new IOException("Failed to get markdown content from Blue Cloud AI");
                    }
                }
            }
        } finally {
            // 计算并记录总耗时
            long endTime = System.currentTimeMillis();
            long duration = endTime - startTime;
            log.info("Blue Cloud AI 处理完成，总耗时: {} 毫秒", duration);
        }
    }

    /**
     * 异步使用Blue Cloud AI上传PDF文件并转换为Markdown
     *
     * @param file PDF文件
     * @param taskId 任务ID
     */
    @Async
    public CompletableFuture<String> uploadByBlueCloudAiAsync(MultipartFile file, String taskId) {
        // 记录开始时间
        long startTime = System.currentTimeMillis();

        try {
            // 更新任务状态为处理中
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            log.info("开始异步使用Blue Cloud AI上传文件: {}", file.getOriginalFilename());

            // 第一步：上传文件到Blue Cloud AI
            // 获取文件字节数组
            byte[] fileBytes = file.getBytes();

            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 20);

            // 创建multipart请求体
            RequestBody requestBody = new MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", file.getOriginalFilename(),
                            RequestBody.create(MediaType.parse(file.getContentType()), fileBytes))
                    .build();

            // 创建请求头
            Request uploadRequest = new Request.Builder()
                    .url(blueCloudAiConfig.getUploadApiUrl())
                    .addHeader("Authorization", blueCloudAiConfig.getAuthToken())
                    .post(requestBody)
                    .build();

            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 40);

            // 执行上传请求
            try (Response uploadResponse = okHttpClient.newCall(uploadRequest).execute()) {
                if (!uploadResponse.isSuccessful()) {
                    log.error("Error uploading file to Blue Cloud AI: {}", uploadResponse);
                    conversionTaskRepository.fail(taskId, "Failed to upload file to Blue Cloud AI: " + uploadResponse.code());
                    return CompletableFuture.completedFuture(null);
                }

                // 解析上传响应
                String uploadResponseBody = uploadResponse.body().string();
                log.info("Blue Cloud AI upload response: {}", uploadResponseBody);

                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 60);

                // 解析上传响应获取文件ID
                BlueCloudAiResponse uploadResult = objectMapper.readValue(uploadResponseBody, BlueCloudAiResponse.class);
                String fileId = uploadResult.getId();
                log.info("文件上传成功，获取到文件ID: {}", fileId);

                // 第二步：请求转换为Markdown
                // 创建JSON请求体
                String jsonBody = String.format("{"
                        + "\"file_id\": \"%s\","
                        + "\"process_figures\": false,"
                        + "\"provider_name\":\"%s\","
                        + "\"img_model\": {"
                        + "\"provider\": \"%s\","
                        + "\"model\": \"%s\","
                        + "\"is_system\": true,"
                        + "\"model_parameters\": {"
                        + "\"temperature\": %s"
                        + "},"
                        + "\"query\": \"%s\""
                        + "}"
                        + "}", fileId, blueCloudAiConfig.getProviderName(), blueCloudAiConfig.getProviderName(),
                        blueCloudAiConfig.getModelName(), blueCloudAiConfig.getTemperature(), blueCloudAiConfig.getQuery());

                RequestBody markdownRequestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);

                // 创建请求头
                Request markdownRequest = new Request.Builder()
                        .url(blueCloudAiConfig.getMarkdownApiUrl())
                        .addHeader("Authorization", blueCloudAiConfig.getAuthToken())
                        .post(markdownRequestBody)
                        .build();

                // 创建带有超时设置的OkHttpClient
                OkHttpClient clientWithTimeout = okHttpClient.newBuilder()
                        .connectTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(120, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .build();

                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 80);

                // 执行Markdown转换请求
                try (Response markdownResponse = clientWithTimeout.newCall(markdownRequest).execute()) {
                    if (!markdownResponse.isSuccessful()) {
                        log.error("Error converting file to Markdown with Blue Cloud AI: {}", markdownResponse);
                        conversionTaskRepository.fail(taskId, "Failed to convert file to Markdown with Blue Cloud AI: " + markdownResponse.code());
                        return CompletableFuture.completedFuture(null);
                    }

                    // 解析Markdown响应
                    String markdownResponseBody = markdownResponse.body().string();
                    log.info("Blue Cloud AI markdown response: {}", markdownResponseBody);

                    // 更新进度
                    conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

                    // 解析Markdown响应获取内容
                    BlueCloudAiMarkdownResponse markdownResult = objectMapper.readValue(markdownResponseBody, BlueCloudAiMarkdownResponse.class);

                    if (markdownResult.getCode() == 0 && markdownResult.getData() != null) {
                        String markdown = markdownResult.getData().getMarkdown_content();

                        // 存储文档
                        Document document = documentRepository.save(
                                file.getOriginalFilename(),
                                null,
                                markdown
                        );

                        // 同时将Markdown内容保存到/doc目录下的MD文件
                        saveMarkdownToFile(markdown, file.getOriginalFilename());

                        // 更新任务状态为完成
                        conversionTaskRepository.complete(taskId, document.getId());
                        return CompletableFuture.completedFuture(document.getId());
                    } else {
                        conversionTaskRepository.fail(taskId, "Failed to get markdown content from Blue Cloud AI");
                        return CompletableFuture.completedFuture(null);
                    }
                }
            }
        } catch (Exception e) {
            log.error("Error processing file with Blue Cloud AI", e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        } finally {
            // 计算并记录总耗时
            long endTime = System.currentTimeMillis();
            long duration = endTime - startTime;
            log.info("Blue Cloud AI 异步处理完成，总耗时: {} 毫秒", duration);
        }
    }
    
    /**
     * 使用sys_paraset表中的OCR参数上传PDF文件并转换为Markdown
     *
     * @param file PDF文件
     * @return 包含文档ID的响应
     * @throws IOException 如果转换过程中发生错误
     */
    public String uploadBySysParasetOcr(File file) throws IOException {
        log.info("开始使用sys_paraset表中的OCR参数上传文件: {}", file.getName());
        
        // 记录开始时间
        long startTime = System.currentTimeMillis();
        
        try {
            // 从sys_paraset表中获取第一个启用的参数集
            SysParaset sysParaset = sysParasetRepository.findAll().stream()
                    .filter(SysParaset::getEnabled)
                    .findFirst()
                    .orElseThrow(() -> new IOException("未找到启用的sys_paraset参数配置"));
            
            // 获取OCR参数JSON字符串
            String ocrParaJson = sysParaset.getOcrPara();
            if (ocrParaJson == null || ocrParaJson.isEmpty()) {
                throw new IOException("sys_paraset表中未配置OCR参数");
            }
            
            // 解析OCR参数JSON
            JsonNode ocrParaNode = objectMapper.readTree(ocrParaJson);
            JsonNode ocrAgentNode = ocrParaNode.get("ocrAgent");
            if (ocrAgentNode == null) {
                throw new IOException("OCR参数中未找到ocrAgent配置");
            }
            
            // 解析AI配置
            JsonNode aiNode = ocrAgentNode.get("ai");
            if (aiNode == null) {
                throw new IOException("OCR参数中未找到AI配置");
            }
            
            String authToken = aiNode.get("authToken").asText();
            String uploadApiUrl = aiNode.get("uploadApiUrl").asText();
            String markdownApiUrl = aiNode.get("markdownApiUrl").asText();
            
            // 解析body配置
            JsonNode bodyNode = ocrAgentNode.get("body");
            if (bodyNode == null) {
                throw new IOException("OCR参数中未找到body配置");
            }
            
            // 读取文件内容
            byte[] fileBytes = Files.readAllBytes(file.toPath());
            String fileName = file.getName();
            String contentType = "application/pdf"; // 默认为PDF类型
            String filePath = file.getParent(); // 获取文件所在目录
            
            // 第一步：上传文件到Blue Cloud AI
            // 创建multipart请求体
            RequestBody requestBody = new MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", fileName,
                            RequestBody.create(MediaType.parse(contentType), fileBytes))
                    .build();
            
            // 创建请求头
            Request uploadRequest = new Request.Builder()
                    .url(uploadApiUrl)
                    .addHeader("Authorization", authToken)
                    .post(requestBody)
                    .build();
            
            // 执行上传请求
            try (Response uploadResponse = okHttpClient.newCall(uploadRequest).execute()) {
                if (!uploadResponse.isSuccessful()) {
                    log.error("Error uploading file to Blue Cloud AI: {}", uploadResponse);
                    throw new IOException("Failed to upload file to Blue Cloud AI: " + uploadResponse.code());
                }
                
                // 解析上传响应
                String uploadResponseBody = uploadResponse.body().string();
                log.info("Blue Cloud AI upload response: {}", uploadResponseBody);
                
                // 解析上传响应获取文件ID
                BlueCloudAiResponse uploadResult = objectMapper.readValue(uploadResponseBody, BlueCloudAiResponse.class);
                String fileId = uploadResult.getId();
                log.info("文件上传成功，获取到文件ID: {}", fileId);
                
                // 第二步：请求转换为Markdown
                // 创建JSON请求体
                // 使用配置中的body模板，只替换file_id
                String bodyTemplate = bodyNode.toString();
                String jsonBody = bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");
                
                RequestBody markdownRequestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);
                
                // 创建请求头
                Request markdownRequest = new Request.Builder()
                        .url(markdownApiUrl)
                        .addHeader("Authorization", authToken)
                        .post(markdownRequestBody)
                        .build();
                
                // 创建带有超时设置的OkHttpClient
                OkHttpClient clientWithTimeout = okHttpClient.newBuilder()
                        .connectTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(120, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .build();
                
                // 执行Markdown转换请求
                try (Response markdownResponse = clientWithTimeout.newCall(markdownRequest).execute()) {
                    if (!markdownResponse.isSuccessful()) {
                        log.error("Error converting file to Markdown with Blue Cloud AI: {}", markdownResponse);
                        throw new IOException("Failed to convert file to Markdown with Blue Cloud AI: " + markdownResponse.code());
                    }
                    
                    // 解析Markdown响应
                    String markdownResponseBody = markdownResponse.body().string();
                    log.info("Blue Cloud AI markdown response: {}", markdownResponseBody);
                    
                    // 解析Markdown响应获取内容
                    BlueCloudAiMarkdownResponse markdownResult = objectMapper.readValue(markdownResponseBody, BlueCloudAiMarkdownResponse.class);
                    
                    if (markdownResult.getCode() == 0 && markdownResult.getData() != null) {
                        String markdown = markdownResult.getData().getMarkdown_content();
                        
                        // 存储文档
                        Document document = documentRepository.save(
                                fileName,
                                null,
                                markdown
                        );
                        
                        // 同时将Markdown内容保存到指定目录下的MD文件
                        saveMarkdownToFile(markdown, fileName, filePath);
                        
                        return document.getId();
                    } else {
                        throw new IOException("Failed to get markdown content from Blue Cloud AI");
                    }
                }
            }
        } finally {
            // 计算并记录总耗时
            long endTime = System.currentTimeMillis();
            long duration = endTime - startTime;
            log.info("使用sys_paraset OCR参数处理完成，总耗时: {} 毫秒", duration);
        }
    }
    
    /**
     * 使用sys_paraset表中的OCR参数上传PDF文件并转换为Markdown（接受File参数）
     *
     * @param originalFile 已保存的原始文件
     * @param document Documents实体对象，用于更新mdContent字段
     * @return 包含文档ID的响应
     * @throws IOException 如果转换过程中发生错误
     */
    public String uploadBySysParasetOcr(java.io.File originalFile, com.linkyoyo.reportaudit.entity.Documents document) throws IOException {
        log.info("开始使用sys_paraset表中的OCR参数上传文件: {}", originalFile.getName());
        
        // 获取原始文件所在目录路径（用于保存MD文件）
        String customSavePath = originalFile.getParent();
        
        // 记录开始时间
        long startTime = System.currentTimeMillis();
        
        try {
            // 从sys_paraset表中获取第一个启用的参数集
            SysParaset sysParaset = sysParasetRepository.findAll().stream()
                    .filter(SysParaset::getEnabled)
                    .findFirst()
                    .orElseThrow(() -> new IOException("未找到启用的sys_paraset参数配置"));
            
            // 获取OCR参数JSON字符串
            String ocrParaJson = sysParaset.getOcrPara();
            if (ocrParaJson == null || ocrParaJson.isEmpty()) {
                throw new IOException("sys_paraset表中未配置OCR参数");
            }
            
            // 解析OCR参数JSON
            JsonNode ocrParaNode = objectMapper.readTree(ocrParaJson);
            JsonNode ocrAgentNode = ocrParaNode.get("ocrAgent");
            if (ocrAgentNode == null) {
                throw new IOException("OCR参数中未找到ocrAgent配置");
            }
            
            // 解析AI配置
            JsonNode aiNode = ocrAgentNode.get("ai");
            if (aiNode == null) {
                throw new IOException("OCR参数中未找到AI配置");
            }
            
            String authToken = aiNode.get("authToken").asText();
            String uploadApiUrl = aiNode.get("uploadApiUrl").asText();
            String markdownApiUrl = aiNode.get("markdownApiUrl").asText();
            
            // 解析body配置
            JsonNode bodyNode = ocrAgentNode.get("body");
            if (bodyNode == null) {
                throw new IOException("OCR参数中未找到body配置");
            }
            
            // 直接使用配置中的body模板，只需要替换file_id
            
            // 获取文件内容
            byte[] fileBytes = java.nio.file.Files.readAllBytes(originalFile.toPath());
            String fileName = originalFile.getName();
            String contentType = getContentTypeByFileName(fileName);
            
            // 第一步：上传文件到Blue Cloud AI
            // 创建multipart请求体
            RequestBody requestBody = new MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", fileName,
                            RequestBody.create(MediaType.parse(contentType), fileBytes))
                    .build();
            
            // 创建请求头
            Request uploadRequest = new Request.Builder()
                    .url(uploadApiUrl)
                    .addHeader("Authorization", authToken)
                    .post(requestBody)
                    .build();
            
            // 执行上传请求
            try (Response uploadResponse = okHttpClient.newCall(uploadRequest).execute()) {
                if (!uploadResponse.isSuccessful()) {
                    log.error("Error uploading file to Blue Cloud AI: {}", uploadResponse);
                    throw new IOException("Failed to upload file to Blue Cloud AI: " + uploadResponse.code());
                }
                
                // 解析上传响应
                String uploadResponseBody = uploadResponse.body().string();
                log.info("Blue Cloud AI upload response: {}", uploadResponseBody);
                
                // 解析上传响应获取文件ID
                BlueCloudAiResponse uploadResult = objectMapper.readValue(uploadResponseBody, BlueCloudAiResponse.class);
                String fileId = uploadResult.getId();
                log.info("文件上传成功，获取到文件ID: {}", fileId);
                
                // 第二步：请求转换为Markdown
                // 创建JSON请求体
                // 使用配置中的body模板，只替换file_id
                String bodyTemplate = bodyNode.toString();
                String jsonBody = bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");
                
                RequestBody markdownRequestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);
                
                // 创建请求头
                Request markdownRequest = new Request.Builder()
                        .url(markdownApiUrl)
                        .addHeader("Authorization", authToken)
                        .post(markdownRequestBody)
                        .build();
                
                // 创建带有超时设置的OkHttpClient
                OkHttpClient clientWithTimeout = okHttpClient.newBuilder()
                        .connectTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(120, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .build();
                
                // 执行Markdown转换请求
                try (Response markdownResponse = clientWithTimeout.newCall(markdownRequest).execute()) {
                    if (!markdownResponse.isSuccessful()) {
                        log.error("Error converting file to Markdown with Blue Cloud AI: {}", markdownResponse);
                        throw new IOException("Failed to convert file to Markdown with Blue Cloud AI: " + markdownResponse.code());
                    }
                    
                    // 解析Markdown响应
                    String markdownResponseBody = markdownResponse.body().string();
                    log.info("Blue Cloud AI markdown response: {}", markdownResponseBody);
                    
                    // 解析Markdown响应获取内容
                    BlueCloudAiMarkdownResponse markdownResult = objectMapper.readValue(markdownResponseBody, BlueCloudAiMarkdownResponse.class);
                    
                    if (markdownResult.getCode() == 0 && markdownResult.getData() != null) {
                        String markdown = markdownResult.getData().getMarkdown_content();
                        
                        // 更新Documents实体的mdContent字段
                        document.setMdContent(markdown);
                        
                        // 将Markdown内容保存到原始文件同级目录下，文件名与原始文件名相同（但扩展名为.md）
                        saveMarkdownToFile(markdown, fileName, customSavePath);
                        
                        return document.getId().toString();
                    } else {
                        throw new IOException("Failed to get markdown content from Blue Cloud AI");
                    }
                }
            }
        } finally {
            // 计算并记录总耗时
            long endTime = System.currentTimeMillis();
            long duration = endTime - startTime;
            log.info("使用sys_paraset OCR参数处理完成，总耗时: {} 毫秒", duration);
        }
    }
    
    /**
     * 异步使用sys_paraset表中的OCR参数上传PDF文件并转换为Markdown
     *
     * @param file PDF文件
     * @param taskId 任务ID
     */
    @Async
    public CompletableFuture<String> uploadBySysParasetOcrAsync(MultipartFile file, String taskId) {
        // 记录开始时间
        long startTime = System.currentTimeMillis();
        
        try {
            // 更新任务状态为处理中
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);
            
            log.info("开始异步使用sys_paraset表中的OCR参数上传文件: {}", file.getOriginalFilename());
            
            // 从sys_paraset表中获取第一个启用的参数集
            SysParaset sysParaset = sysParasetRepository.findAll().stream()
                    .filter(SysParaset::getEnabled)
                    .findFirst()
                    .orElse(null);
            
            if (sysParaset == null) {
                conversionTaskRepository.fail(taskId, "未找到启用的sys_paraset参数配置");
                return CompletableFuture.completedFuture(null);
            }
            
            // 获取OCR参数JSON字符串
            String ocrParaJson = sysParaset.getOcrPara();
            if (ocrParaJson == null || ocrParaJson.isEmpty()) {
                conversionTaskRepository.fail(taskId, "sys_paraset表中未配置OCR参数");
                return CompletableFuture.completedFuture(null);
            }
            
            // 解析OCR参数JSON
            JsonNode ocrParaNode = objectMapper.readTree(ocrParaJson);
            JsonNode ocrAgentNode = ocrParaNode.get("ocrAgent");
            if (ocrAgentNode == null) {
                conversionTaskRepository.fail(taskId, "OCR参数中未找到ocrAgent配置");
                return CompletableFuture.completedFuture(null);
            }
            
            // 解析AI配置
            JsonNode aiNode = ocrAgentNode.get("ai");
            if (aiNode == null) {
                conversionTaskRepository.fail(taskId, "OCR参数中未找到AI配置");
                return CompletableFuture.completedFuture(null);
            }
            
            String authToken = aiNode.get("authToken").asText();
            String uploadApiUrl = aiNode.get("uploadApiUrl").asText();
            String markdownApiUrl = aiNode.get("markdownApiUrl").asText();
            
            // 解析body配置
            JsonNode bodyNode = ocrAgentNode.get("body");
            if (bodyNode == null) {
                conversionTaskRepository.fail(taskId, "OCR参数中未找到body配置");
                return CompletableFuture.completedFuture(null);
            }
            
            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 20);
            
            // 获取文件内容
            byte[] fileBytes = file.getBytes();
            String fileName = file.getOriginalFilename();
            String contentType = file.getContentType();
            
            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 30);
            
            // 第一步：上传文件到Blue Cloud AI
            // 创建multipart请求体
            RequestBody requestBody = new MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", fileName,
                            RequestBody.create(MediaType.parse(contentType), fileBytes))
                    .build();
            
            // 创建请求头
            Request uploadRequest = new Request.Builder()
                    .url(uploadApiUrl)
                    .addHeader("Authorization", authToken)
                    .post(requestBody)
                    .build();
            
            // 更新进度
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 40);
            
            // 执行上传请求
            try (Response uploadResponse = okHttpClient.newCall(uploadRequest).execute()) {
                if (!uploadResponse.isSuccessful()) {
                    log.error("Error uploading file to Blue Cloud AI: {}", uploadResponse);
                    conversionTaskRepository.fail(taskId, "Failed to upload file to Blue Cloud AI: " + uploadResponse.code());
                    return CompletableFuture.completedFuture(null);
                }
                
                // 解析上传响应
                String uploadResponseBody = uploadResponse.body().string();
                log.info("Blue Cloud AI upload response: {}", uploadResponseBody);
                
                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 60);
                
                // 解析上传响应获取文件ID
                BlueCloudAiResponse uploadResult = objectMapper.readValue(uploadResponseBody, BlueCloudAiResponse.class);
                String fileId = uploadResult.getId();
                log.info("文件上传成功，获取到文件ID: {}", fileId);
                
                // 第二步：请求转换为Markdown
                // 创建JSON请求体
                // 使用配置中的body模板，只替换file_id
                String bodyTemplate = bodyNode.toString();
                String jsonBody = bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");
                
                RequestBody markdownRequestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);
                
                // 创建请求头
                Request markdownRequest = new Request.Builder()
                        .url(markdownApiUrl)
                        .addHeader("Authorization", authToken)
                        .post(markdownRequestBody)
                        .build();
                
                // 创建带有超时设置的OkHttpClient
                OkHttpClient clientWithTimeout = okHttpClient.newBuilder()
                        .connectTimeout(60, TimeUnit.SECONDS)
                        .readTimeout(120, TimeUnit.SECONDS)
                        .writeTimeout(60, TimeUnit.SECONDS)
                        .build();
                
                // 更新进度
                conversionTaskRepository.updateStatus(taskId, "PROCESSING", 80);
                
                // 执行Markdown转换请求
                try (Response markdownResponse = clientWithTimeout.newCall(markdownRequest).execute()) {
                    if (!markdownResponse.isSuccessful()) {
                        log.error("Error converting file to Markdown with Blue Cloud AI: {}", markdownResponse);
                        conversionTaskRepository.fail(taskId, "Failed to convert file to Markdown with Blue Cloud AI: " + markdownResponse.code());
                        return CompletableFuture.completedFuture(null);
                    }
                    
                    // 解析Markdown响应
                    String markdownResponseBody = markdownResponse.body().string();
                    log.info("Blue Cloud AI markdown response: {}", markdownResponseBody);
                    
                    // 更新进度
                    conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);
                    
                    // 解析Markdown响应获取内容
                    BlueCloudAiMarkdownResponse markdownResult = objectMapper.readValue(markdownResponseBody, BlueCloudAiMarkdownResponse.class);
                    
                    if (markdownResult.getCode() == 0 && markdownResult.getData() != null) {
                        String markdown = markdownResult.getData().getMarkdown_content();
                        
                        // 存储文档
                        Document document = documentRepository.save(
                                fileName,
                                null,
                                markdown
                        );
                        
                        // 同时将Markdown内容保存到/doc目录下的MD文件
                        saveMarkdownToFile(markdown, fileName);
                        
                        // 更新任务状态为完成
                        conversionTaskRepository.complete(taskId, document.getId());
                        return CompletableFuture.completedFuture(document.getId());
                    } else {
                        conversionTaskRepository.fail(taskId, "Failed to get markdown content from Blue Cloud AI");
                        return CompletableFuture.completedFuture(null);
                    }
                }
            }
        } catch (Exception e) {
            log.error("Error processing file with sys_paraset OCR parameters", e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        } finally {
            // 计算并记录总耗时
            long endTime = System.currentTimeMillis();
            long duration = endTime - startTime;
            log.info("使用sys_paraset OCR参数异步处理完成，总耗时: {} 毫秒", duration);
        }
    }
    
    /**
     * 根据文件名获取对应的ContentType
     *
     * @param fileName 文件名
     * @return ContentType字符串
     */
    private String getContentTypeByFileName(String fileName) {
        if (fileName == null) {
            return "application/octet-stream";
        }
        String lowerFileName = fileName.toLowerCase();
        if (lowerFileName.endsWith(".pdf")) {
            return "application/pdf";
        } else if (lowerFileName.endsWith(".docx")) {
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        } else if (lowerFileName.endsWith(".doc")) {
            return "application/msword";
        } else {
            return "application/octet-stream";
        }
    }




    
    /**
     * 规范化已有#开头的标题
     */
    private String normalizeTitleWithHash(String titleLine) {
        // 提取#符号和标题内容
        int hashCount = 0;
        while (hashCount < titleLine.length() && titleLine.charAt(hashCount) == '#') {
            hashCount++;
        }
        
        String titleContent = titleLine.substring(hashCount).trim();
        
        // 如果标题内容包含章节编号，根据编号确定正确的层级
        if (titleContent.matches("^\\d+(\\.\\d+)*\\s+.*")) {
            int dotCount = countDots(titleContent);
            String correctHashPrefix = generateHashPrefix(dotCount + 1);
            return correctHashPrefix + " " + titleContent;
        }
        
        // 如果是附表类标题，统一使用##
        if (titleContent.contains("附表") || titleContent.contains("附录")) {
            return "## " + titleContent;
        }
        
        // 其他情况保持原有格式，但确保至少有两个#
        if (hashCount < 2) {
            return "## " + titleContent;
        }
        
        return titleLine;
    }

    /**
     * 计算章节层级（通过点的数量）
     */
    private int countDots(String chapterNumber) {
        if ("appendix".equals(chapterNumber)) {
            return 1; // 附表作为二级标题
        }
        
        int dots = 0;
        for (char c : chapterNumber.toCharArray()) {
            if (c == '.') {
                dots++;
            }
        }
        return dots;
    }

    /**
     * 生成对应层级的#前缀
     */
    private String generateHashPrefix(int level) {
        // 限制最大层级为6（Markdown标准）
        level = Math.min(level + 1, 6); // +1是因为我们从##开始（一级用##，二级用###等）
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < level; i++) {
            sb.append("#");
        }
        return sb.toString();
    }

    /**
     * 保存章节整理结果到文件
     * 
     * @param cleanedMdContent 整理后的Markdown内容
     * @param jsonResult 完整的JSON结果
     * @param fileName 原始文件名
     */
    private void saveCleanupResults(String cleanedMdContent, String jsonResult, String fileName) {
        try {
            // 创建输出目录
            String outputDir = "./doc/test";
            Path outputPath = Paths.get(outputDir);
            if (!Files.exists(outputPath)) {
                Files.createDirectories(outputPath);
                log.info("创建输出目录: {}", outputDir);
            }

            // 处理文件名，去除扩展名和路径
            String baseName = new File(fileName).getName();
            if (baseName.contains(".")) {
                baseName = baseName.substring(0, baseName.lastIndexOf('.'));
            }

            // 保存整理后的Markdown内容
            String mdFilePath = outputDir + File.separator + baseName + "_cleaned.md";
            try (FileWriter mdWriter = new FileWriter(mdFilePath)) {
                mdWriter.write(cleanedMdContent);
            }
            log.info("已保存整理后的Markdown内容到: {}", mdFilePath);

            // 保存JSON结果
            String jsonFilePath = outputDir + File.separator + baseName + "_toc.json";
            try (FileWriter jsonWriter = new FileWriter(jsonFilePath)) {
                // 格式化JSON输出
                Object jsonObj = objectMapper.readValue(jsonResult, Object.class);
                String formattedJson = objectMapper.writerWithDefaultPrettyPrinter().writeValueAsString(jsonObj);
                jsonWriter.write(formattedJson);
            }
            log.info("已保存JSON结果到: {}", jsonFilePath);

        } catch (IOException e) {
            log.error("保存章节整理结果时出错", e);
        }
    }
}
