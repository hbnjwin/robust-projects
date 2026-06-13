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

    // ========== SysParaset OCR 配置内部类 ==========

    /**
     * 封装从sys_paraset表加载的OCR配置参数
     */
    private static class SysParasetOcrConfig {
        final String authToken;
        final String uploadApiUrl;
        final String markdownApiUrl;
        final JsonNode bodyNode;

        SysParasetOcrConfig(String authToken, String uploadApiUrl, String markdownApiUrl, JsonNode bodyNode) {
            this.authToken = authToken;
            this.uploadApiUrl = uploadApiUrl;
            this.markdownApiUrl = markdownApiUrl;
            this.bodyNode = bodyNode;
        }
    }

    // ========== 文件保存工具方法 ==========

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

    // ========== 任务管理方法 ==========

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

    // ========== 提取的私有辅助方法 ==========

    /**
     * 安全读取HTTP响应体，防止response.body()为null时的NPE
     *
     * @param response OkHttp响应对象
     * @return 响应体字符串
     * @throws IOException 如果响应体为null或读取失败
     */
    private String getResponseBody(Response response) throws IOException {
        ResponseBody body = response.body();
        if (body == null) {
            throw new IOException("Response body is null, HTTP status: " + response.code());
        }
        return body.string();
    }

    /**
     * 创建带长超时设置的OkHttpClient（用于Markdown转换等耗时请求）
     *
     * @return 配置了60s连接/60s写入/120s读取超时的OkHttpClient
     */
    private OkHttpClient createLongTimeoutClient() {
        return okHttpClient.newBuilder()
                .connectTimeout(60, TimeUnit.SECONDS)
                .readTimeout(120, TimeUnit.SECONDS)
                .writeTimeout(60, TimeUnit.SECONDS)
                .build();
    }

    /**
     * 调用Textin API执行PDF/URL到Markdown的转换
     *
     * @param requestBody 请求体（二进制文件或URL文本）
     * @param queryParams URL查询参数（如 "?image_output_type=base64str"），可为null
     * @return API响应体JSON字符串
     * @throws IOException 如果HTTP请求失败
     */
    private String callTextinApi(RequestBody requestBody, String queryParams) throws IOException {
        String url = textinConfig.getApiUrl() + "/ai/service/v1/pdf_to_markdown"
                + (queryParams != null ? queryParams : "");

        Request request = new Request.Builder()
                .url(url)
                .addHeader("x-ti-app-id", textinConfig.getAppId())
                .addHeader("x-ti-secret-code", textinConfig.getSecretCode())
                .post(requestBody)
                .build();

        try (Response response = okHttpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                log.error("Textin API request failed: {}", response);
                throw new IOException("Textin API request failed: " + response.code());
            }
            String responseBody = getResponseBody(response);
            log.info("Textin API response: {}", responseBody);
            return responseBody;
        }
    }

    /**
     * 解析Textin API响应为完整的TextinResponse DTO（用于同步方法）
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
     * 从Textin API响应中提取Markdown内容（用于异步方法）
     *
     * @param responseBody API响应体JSON字符串
     * @return Markdown内容字符串
     * @throws IOException 如果响应中没有markdown内容
     */
    private String extractTextinMarkdown(String responseBody) throws IOException {
        JsonNode rootNode = objectMapper.readTree(responseBody);
        if (rootNode.has("result") && rootNode.get("result").has("markdown")) {
            return rootNode.get("result").get("markdown").asText();
        }
        throw new IOException("No markdown content in Textin API response");
    }

    /**
     * 上传文件到BlueCloud/SysParaset风格的API（两步转换的第一步）
     *
     * @param fileBytes 文件字节数组
     * @param fileName 文件名
     * @param contentType 文件MIME类型
     * @param uploadUrl 上传API的URL
     * @param authToken 认证令牌
     * @return 上传后获得的文件ID
     * @throws IOException 如果上传失败
     */
    private String uploadToBlueCloud(byte[] fileBytes, String fileName, String contentType,
                                     String uploadUrl, String authToken) throws IOException {
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

        try (Response uploadResponse = okHttpClient.newCall(uploadRequest).execute()) {
            if (!uploadResponse.isSuccessful()) {
                log.error("Error uploading file to cloud API: {}", uploadResponse);
                throw new IOException("Failed to upload file to cloud API: " + uploadResponse.code());
            }

            String uploadResponseBody = getResponseBody(uploadResponse);
            log.info("Cloud AI upload response: {}", uploadResponseBody);

            BlueCloudAiResponse uploadResult = objectMapper.readValue(uploadResponseBody, BlueCloudAiResponse.class);
            String fileId = uploadResult.getId();
            log.info("文件上传成功，获取到文件ID: {}", fileId);
            return fileId;
        }
    }

    /**
     * 请求BlueCloud/SysParaset风格的API将已上传文件转换为Markdown（两步转换的第二步）
     *
     * @param markdownUrl Markdown转换API的URL
     * @param authToken 认证令牌
     * @param jsonBody JSON请求体字符串
     * @return 转换后的Markdown内容
     * @throws IOException 如果转换失败
     */
    private String requestBlueCloudMarkdown(String markdownUrl, String authToken, String jsonBody) throws IOException {
        RequestBody markdownRequestBody = RequestBody.create(MediaType.parse("application/json"), jsonBody);

        Request markdownRequest = new Request.Builder()
                .url(markdownUrl)
                .addHeader("Authorization", authToken)
                .post(markdownRequestBody)
                .build();

        OkHttpClient clientWithTimeout = createLongTimeoutClient();

        try (Response markdownResponse = clientWithTimeout.newCall(markdownRequest).execute()) {
            if (!markdownResponse.isSuccessful()) {
                log.error("Error converting file to Markdown via cloud API: {}", markdownResponse);
                throw new IOException("Failed to convert file to Markdown via cloud API: " + markdownResponse.code());
            }

            String markdownResponseBody = getResponseBody(markdownResponse);
            log.info("Cloud AI markdown response: {}", markdownResponseBody);

            BlueCloudAiMarkdownResponse markdownResult = objectMapper.readValue(markdownResponseBody, BlueCloudAiMarkdownResponse.class);

            if (markdownResult.getCode() == 0 && markdownResult.getData() != null) {
                return markdownResult.getData().getMarkdown_content();
            } else {
                throw new IOException("Failed to get markdown content from cloud API");
            }
        }
    }

    /**
     * 使用BlueCloudAiConfig构建BlueCloud Markdown转换API的JSON请求体
     *
     * @param fileId 已上传文件的ID
     * @return JSON请求体字符串
     */
    private String buildBlueCloudJsonBody(String fileId) {
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
     * 使用SysParaset body模板构建Markdown转换API的JSON请求体
     *
     * @param bodyNode JSON body模板节点
     * @param fileId 已上传文件的ID
     * @return JSON请求体字符串
     */
    private String buildSysParasetJsonBody(JsonNode bodyNode, String fileId) {
        String bodyTemplate = bodyNode.toString();
        return bodyTemplate.replace("\"%s\"", "\"" + fileId + "\"");
    }

    /**
     * 从sys_paraset表加载并验证OCR配置参数
     *
     * @return SysParasetOcrConfig 配置对象
     * @throws IOException 如果配置缺失或无效
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

        JsonNode bodyNode = ocrAgentNode.get("body");
        if (bodyNode == null) {
            throw new IOException("OCR参数中未找到body配置");
        }

        return new SysParasetOcrConfig(
                aiNode.get("authToken").asText(),
                aiNode.get("uploadApiUrl").asText(),
                aiNode.get("markdownApiUrl").asText(),
                bodyNode
        );
    }

    /**
     * 保存转换结果：持久化文档实体并将Markdown写入文件
     *
     * @param markdown Markdown内容
     * @param fileName 文件名
     * @param customPath 自定义保存路径，如果为null则使用默认路径
     * @return 保存的Document对象
     */
    private Document saveConversionResult(String markdown, String fileName, String customPath) {
        Document document = documentRepository.save(fileName, null, markdown);
        saveMarkdownToFile(markdown, fileName, customPath);
        return document;
    }

    // ========== Textin 转换方法 ==========

    /**
     * 异步转换PDF到Markdown（二进制文件上传）
     *
     * @param file PDF文件
     * @param taskId 任务ID
     */
    @Async
    public CompletableFuture<String> convertPdfToMarkdownAsync(MultipartFile file, String taskId) {
        try {
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            RequestBody requestBody = RequestBody.create(MediaType.parse("application/octet-stream"), file.getBytes());

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 30);
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 50);

            String responseBody = callTextinApi(requestBody, "?image_output_type=base64str");

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 70);

            saveJsonResponseToFile(responseBody, file.getOriginalFilename());
            String markdown = extractTextinMarkdown(responseBody);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

            Document document = saveConversionResult(markdown, file.getOriginalFilename(), null);
            conversionTaskRepository.complete(taskId, document.getId());
            return CompletableFuture.completedFuture(document.getId());
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
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            RequestBody requestBody = RequestBody.create(MediaType.parse("text/plain"), fileUrl);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 30);
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 50);

            String responseBody = callTextinApi(requestBody, "?image_output_type=base64str");

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 70);

            String docName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
            saveJsonResponseToFile(responseBody, docName);
            String markdown = extractTextinMarkdown(responseBody);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

            Document document = saveConversionResult(markdown, docName, null);
            conversionTaskRepository.complete(taskId, document.getId());
            return CompletableFuture.completedFuture(document.getId());
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
        RequestBody requestBody = RequestBody.create(MediaType.parse("application/octet-stream"), file.getBytes());

        String responseBody = callTextinApi(requestBody, "?image_output_type=base64str&get_image=objects");
        saveJsonResponseToFile(responseBody, file.getOriginalFilename());

        TextinResponse textinResponse = parseTextinResponse(responseBody);

        if (textinResponse.getResult() != null && textinResponse.getResult().getMarkdown() != null) {
            saveConversionResult(textinResponse.getResult().getMarkdown(), file.getOriginalFilename(), null);
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

        String responseBody = callTextinApi(requestBody, null);

        String docName = fileName != null ? fileName : fileUrl.substring(fileUrl.lastIndexOf('/') + 1);
        saveJsonResponseToFile(responseBody, docName);

        TextinResponse textinResponse = parseTextinResponse(responseBody);

        if (textinResponse.getResult() != null && textinResponse.getResult().getMarkdown() != null) {
            saveConversionResult(textinResponse.getResult().getMarkdown(), docName, null);
        }

        return textinResponse;
    }

    // ========== Blue Cloud AI 转换方法 ==========

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
        long startTime = System.currentTimeMillis();

        try {
            log.info("ai phrase model:{}", blueCloudAiConfig.getProviderName());

            String fileId = uploadToBlueCloud(fileBytes, fileName, contentType,
                    blueCloudAiConfig.getUploadApiUrl(), blueCloudAiConfig.getAuthToken());

            String jsonBody = buildBlueCloudJsonBody(fileId);
            String markdown = requestBlueCloudMarkdown(
                    blueCloudAiConfig.getMarkdownApiUrl(), blueCloudAiConfig.getAuthToken(), jsonBody);

            Document document = saveConversionResult(markdown, fileName, customPath);
            return document.getId();
        } finally {
            long duration = System.currentTimeMillis() - startTime;
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
        long startTime = System.currentTimeMillis();

        try {
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            log.info("开始异步使用Blue Cloud AI上传文件: {}", file.getOriginalFilename());
            byte[] fileBytes = file.getBytes();

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 20);
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 40);

            String fileId = uploadToBlueCloud(fileBytes, file.getOriginalFilename(), file.getContentType(),
                    blueCloudAiConfig.getUploadApiUrl(), blueCloudAiConfig.getAuthToken());

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 60);

            String jsonBody = buildBlueCloudJsonBody(fileId);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 80);

            String markdown = requestBlueCloudMarkdown(
                    blueCloudAiConfig.getMarkdownApiUrl(), blueCloudAiConfig.getAuthToken(), jsonBody);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

            Document document = saveConversionResult(markdown, file.getOriginalFilename(), null);
            conversionTaskRepository.complete(taskId, document.getId());
            return CompletableFuture.completedFuture(document.getId());
        } catch (Exception e) {
            log.error("Error processing file with Blue Cloud AI", e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        } finally {
            long duration = System.currentTimeMillis() - startTime;
            log.info("Blue Cloud AI 异步处理完成，总耗时: {} 毫秒", duration);
        }
    }

    // ========== SysParaset OCR 转换方法 ==========

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
            String fileId = uploadToBlueCloud(fileBytes, file.getName(), "application/pdf",
                    config.uploadApiUrl, config.authToken);

            String jsonBody = buildSysParasetJsonBody(config.bodyNode, fileId);
            String markdown = requestBlueCloudMarkdown(config.markdownApiUrl, config.authToken, jsonBody);

            Document document = saveConversionResult(markdown, file.getName(), file.getParent());
            return document.getId();
        } finally {
            long duration = System.currentTimeMillis() - startTime;
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
        String customSavePath = originalFile.getParent();
        long startTime = System.currentTimeMillis();

        try {
            SysParasetOcrConfig config = loadSysParasetOcrConfig();

            byte[] fileBytes = Files.readAllBytes(originalFile.toPath());
            String contentType = getContentTypeByFileName(originalFile.getName());
            String fileId = uploadToBlueCloud(fileBytes, originalFile.getName(), contentType,
                    config.uploadApiUrl, config.authToken);

            String jsonBody = buildSysParasetJsonBody(config.bodyNode, fileId);
            String markdown = requestBlueCloudMarkdown(config.markdownApiUrl, config.authToken, jsonBody);

            // 此重载方法更新已有Documents实体，而非创建新Document
            document.setMdContent(markdown);
            saveMarkdownToFile(markdown, originalFile.getName(), customSavePath);

            return document.getId().toString();
        } finally {
            long duration = System.currentTimeMillis() - startTime;
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
        long startTime = System.currentTimeMillis();

        try {
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 10);

            log.info("开始异步使用sys_paraset表中的OCR参数上传文件: {}", file.getOriginalFilename());
            SysParasetOcrConfig config = loadSysParasetOcrConfig();

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 20);

            byte[] fileBytes = file.getBytes();

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 30);
            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 40);

            String fileId = uploadToBlueCloud(fileBytes, file.getOriginalFilename(), file.getContentType(),
                    config.uploadApiUrl, config.authToken);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 60);

            String jsonBody = buildSysParasetJsonBody(config.bodyNode, fileId);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 80);

            String markdown = requestBlueCloudMarkdown(config.markdownApiUrl, config.authToken, jsonBody);

            conversionTaskRepository.updateStatus(taskId, "PROCESSING", 90);

            Document doc = saveConversionResult(markdown, file.getOriginalFilename(), null);
            conversionTaskRepository.complete(taskId, doc.getId());
            return CompletableFuture.completedFuture(doc.getId());
        } catch (Exception e) {
            log.error("Error processing file with sys_paraset OCR parameters", e);
            conversionTaskRepository.fail(taskId, e.getMessage());
            return CompletableFuture.completedFuture(null);
        } finally {
            long duration = System.currentTimeMillis() - startTime;
            log.info("使用sys_paraset OCR参数异步处理完成，总耗时: {} 毫秒", duration);
        }
    }

    // ========== 工具方法 ==========

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
