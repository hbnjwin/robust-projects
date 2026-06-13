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

    // ==================== 内部接口和类 ====================

    /**
     * 异步转换操作的函数式接口
     */
    @FunctionalInterface
    private interface AsyncConversionOperation {
        /**
         * 执行异步转换操作
         *
         * @param taskId 任务ID
         * @return 文档ID，如果操作已在内部处理了失败则返回null
         * @throws Exception 如果转换过程中发生错误
         */
        String execute(String taskId) throws Exception;
    }

    /**
     * SysParaset OCR配置，从数据库加载
     */
    private static class SysParasetOcrConfig {
        final String authToken;
        final String uploadApiUrl;
        final String markdownApiUrl;
        final String bodyTemplate;

        SysParasetOcrConfig(String authToken, String uploadApiUrl, String markdownApiUrl, String bodyTemplate) {
            this.authToken = authToken;
            this.uploadApiUrl = uploadApiUrl;
            this.markdownApiUrl = markdownApiUrl;
            this.bodyTemplate = bodyTemplate;
        }
    }

    // ==================== 文件操作辅助方法 ====================

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

    // ==================== HTTP 辅助方法 ====================

    /**
     * 执行HTTP请求并返回响应体字符串
     *
     * @param request HTTP请求
     * @param operationName 操作名称（用于日志）
     * @return 响应体字符串
     * @throws IOException 如果请求失败或响应体为空
     */
    private String executeHttpRequest(Request request, String operationName) throws IOException {
        try (Response response = okHttpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                log.error("Error during {}: {}", operationName, response);
                throw new IOException("Failed during " + operationName + ": " + response.code());
            }
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("Empty response body during " + operationName);
            }
            String responseBody = body.string();
            log.info("{} response: {}", operationName, responseBody);
            return responseBody;
        }
    }

    /**
     * 执行HTTP请求（使用60s连接/120s读取超时），用于两步流程的转换步骤
     *
     * @param request HTTP请求
     * @param operationName 操作名称（用于日志）
     * @return 响应体字符串
     * @throws IOException 如果请求失败或响应体为空
     */
    private String executeHttpRequestWithTimeout(Request request, String operationName) throws IOException {
        OkHttpClient clientWithTimeout = okHttpClient.newBuilder()
                .connectTimeout(60, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .build();
        try (Response response = clientWithTimeout.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                log.error("Error during {}: {}", operationName, response);
                throw new IOException("Failed during " + operationName + ": " + response.code());
            }
            ResponseBody body = response.body();
            if (body == null) {
                throw new IOException("Empty response body during " + operationName);
            }
            String responseBody = body.string();
            log.info("{} response: {}", operationName, responseBody);
            return responseBody;
        }
    }

    /**
     * 构建带有Textin认证头的请求
     *
     * @param url 请求URL
     * @param body 请求体
     * @return OkHttp Request对象
     */
    private Request buildTextinRequest(String url, RequestBody body) {
        return new Request.Builder()
                .url(url)
                .addHeader("x-ti-app-id", textinConfig.getAppId())
                .addHeader("x-ti-secret-code", textinConfig.getSecretCode())
                .post(body)
                .build();
    }

    // ==================== Textin 解析辅助方法 ====================

    /**
     * 解析Textin API响应为完整的TextinResponse对象
     *
     * @param responseBody API响应体JSON字符串
     * @return TextinResponse对象
     * @throws IOException 如果JSON解析失败
     */
    private TextinResponse parseTextinResponse(String responseBody) throws IOException {
        JsonNode rootNode = objectMapper.readTree(responseBody);
        TextinResponse textinResponse = new TextinResponse();

        if (rootNode.has("duration")) {
            textinResponse.setDuration(rootNode.get("duration").asInt());
        }
        if (rootNode.has("message")) {
            textinResponse.setMessage(rootNode.get("message").asText());
        }

        if (rootNode.has("result")) {
            JsonNode resultNode = rootNode.get("result");
            TextinResponse.TextinResult result = new TextinResponse.TextinResult();

            if (resultNode.has("markdown")) {
                result.setMarkdown(resultNode.get("markdown").asText());
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

    /**
     * 从Textin API响应中提取markdown内容
     *
     * @param responseBody API响应体JSON字符串
     * @return markdown内容，如果未找到则返回null
     * @throws IOException 如果JSON解析失败
     */
    private String extractTextinMarkdown(String responseBody) throws IOException {
        JsonNode rootNode = objectMapper.readTree(responseBody);
        if (rootNode.has("result") && rootNode.get("result").has("markdown")) {
            return rootNode.get("result").get("markdown").asText();
        }
        return null;
    }

    // ==================== 两步流程辅助方法（BlueCloud / SysParaset） ====================

    /**
     * 上传文件到远程服务并返回文件ID
     *
     * @param uploadUrl 上传API地址
     * @param authToken 认证令牌
     * @param fileBytes 文件字节数组
     * @param fileName 文件名
     * @param contentType 内容类型
     * @return 文件ID
     * @throws IOException 如果上传失败
     */
    private String uploadFileToRemote(String uploadUrl, String authToken,
                                       byte[] fileBytes, String fileName,
                                       String contentType) throws IOException {
        RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", fileName,
                        RequestBody.create(MediaType.parse(contentType), fileBytes))
                .build();

        Request uploadRequest = new Request.Builder()
                .url(uploadUrl)
                .addHeader("Authorization", authToken)
                .post(requestBody)
                .build();

        String responseBody = executeHttpRequest(uploadRequest, "file upload");

        BlueCloudAiResponse uploadResult = objectMapper.readValue(responseBody, BlueCloudAiResponse.class);
        String fileId = uploadResult.getId();
        log.info("文件上传成功，获取到文件ID: {}", fileId);
        return fileId;
    }

    /**
     * 执行Markdown转换请求并返回markdown内容
     *
     * @param markdownUrl 转换API地址
     * @param authToken 认证令牌
     * @param jsonBody 请求体JSON字符串
     * @return markdown内容
     * @throws IOException 如果转换失败
     */
    private String executeMarkdownConversion(String markdownUrl, String authToken,
                                              String jsonBody) throws IOException {
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);

        Request request = new Request.Builder()
                .url(markdownUrl)
                .addHeader("Authorization", authToken)
                .post(requestBody)
                .build();

        String responseBody = executeHttpRequestWithTimeout(request, "markdown conversion");

        BlueCloudAiMarkdownResponse result = objectMapper.readValue(responseBody, BlueCloudAiMarkdownResponse.class);
        if (result.getCode() == 0 && result.getData() != null) {
            return result.getData().getMarkdown_content();
        }
        throw new IOException("Failed to get markdown content from conversion API");
    }

    /**
     * 构建BlueCloud同步版转换请求体
     * 注意：同步版使用 "name" + "completion_params" + 硬编码 "azure_openai"
     * （与异步版字段名不同，这是已知的接口差异）
     *
     * @param fileId 文件ID
     * @return JSON请求体字符串
     */
    private String buildBlueCloudSyncConvertBody(String fileId) {
        return String.format("{"
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
    }

    /**
     * 构建BlueCloud异步版转换请求体
     * 注意：异步版使用 "model" + "model_parameters" + 动态provider
     * （与同步版字段名不同，这是已知的接口差异）
     *
     * @param fileId 文件ID
     * @return JSON请求体字符串
     */
    private String buildBlueCloudAsyncConvertBody(String fileId) {
        return String.format("{"
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
    }

    // ==================== 保存辅助方法 ====================

    /**
     * 保存文档实体和Markdown文件，返回文档ID
     *
     * @param markdown markdown内容
     * @param fileName 文件名
     * @param customPath 自定义保存路径，null则使用默认路径
     * @return 文档ID
     */
    private String saveDocumentAndMarkdown(String markdown, String fileName, String customPath) {
        Document document = documentRepository.save(fileName, null, markdown);
        saveMarkdownToFile(markdown, fileName, customPath);
        return document.getId();
    }

    // ==================== SysParaset 配置加载 ====================

    /**
     * 从sys_paraset表加载启用的OCR配置
     *
     * @return SysParasetOcrConfig配置对象
     * @throws IOException 如果未找到启用的配置或配置不完整
     */
    private SysParasetOcrConfig loadSysParasetOcrConfig() throws IOException {
        SysParaset sysParaset = sysParasetRepository.findAll().stream()
                .filter(SysParaset::getEnabled)
                .findFirst()
                .orElseThrow(() -> new IOException("未找到启用的sys_paraset参数配置"));

        String ocrParaJson = sysParaset.getOcrPara();
        if (ocrParaJson == null || ocrParaJson.isEmpty()) {
            throw new IOException("sys_paraset表中未配置OCR参数");
        }

        JsonNode ocrParaNode = objectMapper.readTree(ocrParaJson);
        JsonNode ocrAgentNode = ocrParaNode.get("ocrAgent");
        if (ocrAgentNode == null) {
            throw new IOException("OCR参数中未找到ocrAgent配置");
        }

        JsonNode aiNode = ocrAgentNode.get("ai");
        if (aiNode == null) {
            throw new IOException("OCR参数中未找到AI配置");
        }

        String authToken = aiNode.get("authToken").asText();
        String uploadApiUrl = aiNode.get("uploadApiUrl").asText();
        String markdownApiUrl = aiNode.get("markdownApiUrl").asText();

        JsonNode bodyNode = ocrAgentNode.get("body");
        if (bodyNode == null) {
            throw new IOException("OCR参数中未找到body配置");
        }

        return new SysParasetOcrConfig(authToken, uploadApiUrl, markdownApiUrl, bodyNode.toString());
    }

    // ==================== 异步执行包装器 ====================

    /**
     * 执行异步转换操作的通用包装器，处理异常捕获、任务完成/失败和耗时日志
     *
     * @param taskId 任务ID
     * @param operationName 操作名称（用于日志）
     * @param operation 转换操作
     * @return CompletableFuture包含文档ID或null
     */
    private CompletableFuture<String> executeAsyncConversion(String taskId, String operationName,
                                                              AsyncConversionOperation operation) {
        long startTime = System.currentTimeMillis();
        try {
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            String docId = operation.execute(taskId);
            if (docId != null) {
                conversionTaskRepository.complete(taskId, docId);
            }
            return CompletableFuture.completedFuture(docId);
        } catch (Exception e) {
            log.error("Error in {}", operationName, e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        } finally {
            log.info("{}完成，总耗时: {} 毫秒", operationName, System.currentTimeMillis() - startTime);
        }
    }

    // ==================== 公共方法：任务管理 ====================

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

    // ==================== 公共方法：Textin API 转换 ====================

    /**
     * 异步转换PDF到Markdown（二进制文件上传）
     *
     * @param file PDF文件
     * @param taskId 任务ID
     */
    @Async
    public CompletableFuture<String> convertPdfToMarkdownAsync(MultipartFile file, String taskId) {
        return executeAsyncConversion(taskId, "Textin PDF转换", (tid) -> {
            byte[] fileBytes = file.getBytes();
            RequestBody requestBody = RequestBody.create(MediaType.parse("application/octet-stream"), fileBytes);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 30);

            String url = textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown?image_output_type=base64str";
            Request request = buildTextinRequest(url, requestBody);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 50);

            String responseBody = executeHttpRequest(request, "Textin PDF conversion");

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 70);

            saveJsonResponseToFile(responseBody, file.getOriginalFilename());

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 90);

            String markdown = extractTextinMarkdown(responseBody);
            if (markdown == null) {
                conversionTaskRepository.fail(tid, "Failed to convert PDF to Markdown: No markdown content");
                return null;
            }

            return saveDocumentAndMarkdown(markdown, file.getOriginalFilename(), null);
        });
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
        return executeAsyncConversion(taskId, "Textin URL转换", (tid) -> {
            RequestBody requestBody = RequestBody.create(MediaType.parse("text/plain"), fileUrl);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 30);

            String url = textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown?image_output_type=base64str";
            Request request = buildTextinRequest(url, requestBody);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 50);

            String responseBody = executeHttpRequest(request, "Textin URL conversion");

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 70);

            String docName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
            saveJsonResponseToFile(responseBody, docName);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 90);

            String markdown = extractTextinMarkdown(responseBody);
            if (markdown == null) {
                conversionTaskRepository.fail(tid, "Failed to convert URL to Markdown: No markdown content");
                return null;
            }

            return saveDocumentAndMarkdown(markdown, docName, null);
        });
    }

    /**
     * 同步转换PDF到Markdown（二进制文件上传）
     *
     * @param file PDF文件
     * @return TextinResponse 包含转换结果
     * @throws IOException 如果转换过程中发生错误
     */
    public TextinResponse convertPdfToMarkdown(MultipartFile file) throws IOException {
        byte[] fileBytes = file.getBytes();

        RequestBody requestBody = RequestBody.create(MediaType.parse("application/octet-stream"), fileBytes);

        String url = textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown?image_output_type=base64str&get_image=objects";
        Request request = buildTextinRequest(url, requestBody);

        String responseBody = executeHttpRequest(request, "Textin PDF conversion");

        saveJsonResponseToFile(responseBody, file.getOriginalFilename());

        TextinResponse textinResponse = parseTextinResponse(responseBody);

        if (textinResponse.getResult() != null && textinResponse.getResult().getMarkdown() != null) {
            saveDocumentAndMarkdown(textinResponse.getResult().getMarkdown(), file.getOriginalFilename(), null);
        }

        return textinResponse;
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
        RequestBody requestBody = RequestBody.create(MediaType.parse("text/plain"), fileUrl);

        String url = textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown";
        Request request = buildTextinRequest(url, requestBody);

        String responseBody = executeHttpRequest(request, "Textin URL conversion");

        String docName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
        saveJsonResponseToFile(responseBody, docName);

        TextinResponse textinResponse = parseTextinResponse(responseBody);

        if (textinResponse.getResult() != null && textinResponse.getResult().getMarkdown() != null) {
            saveDocumentAndMarkdown(textinResponse.getResult().getMarkdown(), docName, null);
        }

        return textinResponse;
    }

    // ==================== 公共方法：Blue Cloud AI 转换 ====================

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
     * 内部方法：使用Blue Cloud AI上传文件并转换为Markdown
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

        long startTime = System.currentTimeMillis();
        try {
            // 第一步：上传文件
            String fileId = uploadFileToRemote(
                    blueCloudAiConfig.getUploadApiUrl(), blueCloudAiConfig.getAuthToken(),
                    fileBytes, fileName, contentType);

            log.info("ai phrase model:{}", blueCloudAiConfig.getProviderName());

            // 第二步：请求转换为Markdown（同步版JSON字段：name + completion_params + 硬编码azure_openai）
            String jsonBody = buildBlueCloudSyncConvertBody(fileId);
            String markdown = executeMarkdownConversion(
                    blueCloudAiConfig.getMarkdownApiUrl(), blueCloudAiConfig.getAuthToken(), jsonBody);

            return saveDocumentAndMarkdown(markdown, fileName, customPath);
        } finally {
            log.info("Blue Cloud AI 处理完成，总耗时: {} 毫秒", System.currentTimeMillis() - startTime);
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
        return executeAsyncConversion(taskId, "BlueCloud异步转换", (tid) -> {
            log.info("开始异步使用Blue Cloud AI上传文件: {}", file.getOriginalFilename());

            byte[] fileBytes = file.getBytes();

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 20);

            // 第一步：上传文件
            String fileId = uploadFileToRemote(
                    blueCloudAiConfig.getUploadApiUrl(), blueCloudAiConfig.getAuthToken(),
                    fileBytes, file.getOriginalFilename(), file.getContentType());

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 60);

            // 第二步：请求转换为Markdown（异步版JSON字段：model + model_parameters + 动态provider）
            String jsonBody = buildBlueCloudAsyncConvertBody(fileId);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 80);

            String markdown = executeMarkdownConversion(
                    blueCloudAiConfig.getMarkdownApiUrl(), blueCloudAiConfig.getAuthToken(), jsonBody);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 90);

            return saveDocumentAndMarkdown(markdown, file.getOriginalFilename(), null);
        });
    }

    // ==================== 公共方法：SysParaset OCR 转换 ====================

    /**
     * 使用sys_paraset表中的OCR参数上传PDF文件并转换为Markdown
     *
     * @param file PDF文件
     * @return 包含文档ID的响应
     * @throws IOException 如果转换过程中发生错误
     */
    public String uploadBySysParasetOcr(File file) throws IOException {
        log.info("开始使用sys_paraset表中的OCR参数上传文件: {}", file.getName());

        long startTime = System.currentTimeMillis();
        try {
            SysParasetOcrConfig config = loadSysParasetOcrConfig();

            byte[] fileBytes = Files.readAllBytes(file.toPath());
            String fileName = file.getName();

            // 第一步：上传文件
            String fileId = uploadFileToRemote(
                    config.uploadApiUrl, config.authToken,
                    fileBytes, fileName, "application/pdf");

            // 第二步：使用body模板替换file_id并转换
            String jsonBody = config.bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");
            String markdown = executeMarkdownConversion(config.markdownApiUrl, config.authToken, jsonBody);

            return saveDocumentAndMarkdown(markdown, fileName, file.getParent());
        } finally {
            log.info("使用sys_paraset OCR参数处理完成，总耗时: {} 毫秒", System.currentTimeMillis() - startTime);
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

        String customSavePath = originalFile.getParent();
        long startTime = System.currentTimeMillis();

        try {
            SysParasetOcrConfig config = loadSysParasetOcrConfig();

            byte[] fileBytes = Files.readAllBytes(originalFile.toPath());
            String fileName = originalFile.getName();
            String contentType = getContentTypeByFileName(fileName);

            // 第一步：上传文件
            String fileId = uploadFileToRemote(
                    config.uploadApiUrl, config.authToken,
                    fileBytes, fileName, contentType);

            // 第二步：使用body模板替换file_id并转换
            String jsonBody = config.bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");
            String markdown = executeMarkdownConversion(config.markdownApiUrl, config.authToken, jsonBody);

            // 更新Documents实体的mdContent字段（注意：此方法不创建新文档，而是更新已有实体）
            document.setMdContent(markdown);
            saveMarkdownToFile(markdown, fileName, customSavePath);

            return document.getId().toString();
        } finally {
            log.info("使用sys_paraset OCR参数处理完成，总耗时: {} 毫秒", System.currentTimeMillis() - startTime);
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
        return executeAsyncConversion(taskId, "SysParaset异步转换", (tid) -> {
            log.info("开始异步使用sys_paraset表中的OCR参数上传文件: {}", file.getOriginalFilename());

            SysParasetOcrConfig config = loadSysParasetOcrConfig();

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 20);

            byte[] fileBytes = file.getBytes();
            String fileName = file.getOriginalFilename();

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 30);

            // 第一步：上传文件
            String fileId = uploadFileToRemote(
                    config.uploadApiUrl, config.authToken,
                    fileBytes, fileName, file.getContentType());

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 60);

            // 第二步：使用body模板替换file_id并转换
            String jsonBody = config.bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 80);

            String markdown = executeMarkdownConversion(config.markdownApiUrl, config.authToken, jsonBody);

            conversionTaskRepository.updateStatus(tid, "PROCESSING", 90);

            return saveDocumentAndMarkdown(markdown, fileName, null);
        });
    }

    // ==================== 工具方法 ====================

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
