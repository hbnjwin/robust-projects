package com.linkyoyo.reportaudit.controller;

import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.service.AiService;
import com.linkyoyo.reportaudit.result.R;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.validation.constraints.NotNull;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * AI 服务控制器
 */
@RestController
@RequestMapping("/agentAi")
@Slf4j
public class AiController {

    @Autowired
    private AiConfig aiConfig;

    @Autowired
    private AiService aiService;

    /**
     * 调用Azure OpenAI服务解析内容
     *
     * @param content 需要解析的内容
     * @return 解析结果
     */
    @PostMapping("/azure")
    public R callAzureAi(@RequestBody String content) {
        try {
            Map<String, Object> resultMap = aiService.callAzureAi(content);
            return R.ok(resultMap);
        } catch (RuntimeException e) {
            log.error("调用Azure AI失败: {}", e.getMessage());
            return R.warning(e.getMessage());
        }
    }

    /**
     * 调用DeepSeek AI服务解析内容
     *
     * @param content 需要解析的内容
     * @return 解析结果
     */
    @PostMapping("/deepseek")
    public R callDeepSeekAi(@RequestBody String content) {
        try {
            Map<String, Object> resultMap = aiService.callDeepSeekAi(content);
            return R.ok(resultMap);
        } catch (RuntimeException e) {
            log.error("调用DeepSeek AI失败: {}", e.getMessage());
            return R.warning(e.getMessage());
        }
    }

    /**
     * 获取当前AI配置信息
     *
     * @return 配置信息
     */
    @GetMapping("/config")
    public R getAiConfig() {
        Map<String, Object> config = new HashMap<>();

        // Azure配置
        Map<String, Object> azure = new HashMap<>();
        azure.put("isAzure", aiConfig.isAzure());
        azure.put("url", aiConfig.getUrl());
        azure.put("model", aiConfig.getModel());
        azure.put("version", aiConfig.getVersion());

        // DeepSeek配置
        Map<String, Object> deepseek = new HashMap<>();
        deepseek.put("isAzure", aiConfig.isDeepseekIsAzure());
        deepseek.put("url", aiConfig.getDeepseekUrl());
        deepseek.put("model", aiConfig.getDeepseekModel());

        config.put("azure", azure);
        config.put("deepseek", deepseek);

        return R.ok(config);
    }

    /**
     * 上传并使用AI解析Markdown文件
     *
     * @param file 上传的Markdown文件
     * @param useDeepSeek 是否使用DeepSeek AI (默认为false，使用Azure)
     * @return AI解析结果
     */
    @PostMapping("/uploadMd")
    public R uploadAndAnalyzeMd(
            @NotNull @RequestParam("file") MultipartFile file,
            @RequestParam(value = "useDeepSeek", defaultValue = "false") boolean useDeepSeek) {

        if (file.isEmpty()) {
            return R.warning("上传的文件为空");
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || (!originalFilename.endsWith(".md") && !originalFilename.endsWith(".markdown"))) {
            return R.warning("只支持上传Markdown文件(.md或.markdown)");
        }

        try {
            String markdownContent = new String(file.getBytes());
            Map<String, Object> resultMap = aiService.uploadAndAnalyzeMd(markdownContent, originalFilename, useDeepSeek);
            return R.ok(resultMap);
        } catch (RuntimeException e) {
            log.error("AI解析失败: {}", e.getMessage());
            return R.warning(e.getMessage());
        } catch (IOException e) {
            log.error("处理上传文件失败: {}", originalFilename, e);
            return R.warning("处理上传文件失败: " + e.getMessage());
        }
    }

    /**
     * 上传MD文件并调用callAi方法解析内容
     *
     * @param file 上传的MD文件
     * @return AI解析结果
     */
    @PostMapping("/uploadMdToCallAi")
    public R uploadMdToCallAi(@NotNull @RequestParam("file") MultipartFile file) {
        if (file.isEmpty()) {
            return R.warning("上传的文件为空");
        }

        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || (!originalFilename.endsWith(".md") && !originalFilename.endsWith(".markdown"))) {
            return R.warning("只支持上传Markdown文件(.md或.markdown)");
        }

        try {
            String markdownContent = new String(file.getBytes());
            Map<String, Object> resultMap = aiService.uploadMdToCallAi(markdownContent, originalFilename);
            return R.ok(resultMap);
        } catch (RuntimeException e) {
            log.error("AI解析失败: {}", e.getMessage());
            return R.warning(e.getMessage());
        } catch (IOException e) {
            log.error("处理上传文件失败: {}", originalFilename, e);
            return R.warning("处理上传文件失败: " + e.getMessage());
        }
    }
}
