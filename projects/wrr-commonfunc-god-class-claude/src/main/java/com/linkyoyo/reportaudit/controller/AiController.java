package com.linkyoyo.reportaudit.controller;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.support.AiService;
import com.linkyoyo.reportaudit.result.R;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
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

    @Value("${paraSet.tempPath:temp}")
    private String tempPath;

    @PostMapping("/azure")
    public R callAzureAi(@RequestBody String content) {
        log.info("接收到Azure AI请求，内容长度: {}", content.length());
        log.info("当前Azure配置 - URL: {}, Model: {}, Version: {}", aiConfig.getUrl(), aiConfig.getModel(), aiConfig.getVersion());

        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");

        log.info("处理后的内容长度: {}", content.length());

        JSONObject result = aiService.callAiWithOkHttp(content);

        if (result.containsKey("error")) {
            log.error("调用Azure AI失败: {}", result.getStr("error"));
            return R.warning(result.getStr("error"));
        }

        Map<String, Object> resultMap = new HashMap<>();
        for (String key : result.keySet()) {
            Object value = result.get(key);
            if (value instanceof cn.hutool.json.JSONNull) {
                resultMap.put(key, null);
            } else {
                resultMap.put(key, value);
            }
        }

        return R.ok(resultMap);
    }

    @PostMapping("/deepseek")
    public R callDeepSeekAi(@RequestBody String content) {
        log.info("接收到DeepSeek AI请求，内容长度: {}", content.length());
        log.info("当前DeepSeek配置 - URL: {}, Model: {}", aiConfig.getDeepseekUrl(), aiConfig.getDeepseekModel());

        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");

        log.info("处理后的内容长度: {}", content.length());

        JSONObject result = aiService.callDeepSeekAi(content);

        if (result.containsKey("error")) {
            log.error("调用DeepSeek AI失败: {}", result.getStr("error"));
            return R.warning(result.getStr("error"));
        }

        Map<String, Object> resultMap = new HashMap<>();
        for (String key : result.keySet()) {
            Object value = result.get(key);
            if (value instanceof cn.hutool.json.JSONNull) {
                resultMap.put(key, null);
            } else {
                resultMap.put(key, value);
            }
        }

        return R.ok(resultMap);
    }

    @GetMapping("/config")
    public R getAiConfig() {
        Map<String, Object> config = new HashMap<>();

        Map<String, Object> azure = new HashMap<>();
        azure.put("isAzure", aiConfig.isAzure());
        azure.put("url", aiConfig.getUrl());
        azure.put("model", aiConfig.getModel());
        azure.put("version", aiConfig.getVersion());

        Map<String, Object> deepseek = new HashMap<>();
        deepseek.put("isAzure", aiConfig.isDeepseekIsAzure());
        deepseek.put("url", aiConfig.getDeepseekUrl());
        deepseek.put("model", aiConfig.getDeepseekModel());

        config.put("azure", azure);
        config.put("deepseek", deepseek);

        return R.ok(config);
    }

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
            log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

            JSONObject result;
            if (useDeepSeek) {
                log.info("使用DeepSeek AI解析Markdown文件: {}", originalFilename);
                result = aiService.callDeepSeekAi(markdownContent);
            } else {
                log.info("使用Azure AI解析Markdown文件: {}", originalFilename);
                result = aiService.callAiWithOkHttp(markdownContent);
            }

            if (result.containsKey("error")) {
                log.error("AI解析失败: {}", result.getStr("error"));
                return R.warning(result.getStr("error"));
            }

            Map<String, Object> resultMap = new HashMap<>();
            for (String key : result.keySet()) {
                Object value = result.get(key);
                if (value instanceof cn.hutool.json.JSONNull) {
                    resultMap.put(key, null);
                } else {
                    resultMap.put(key, value);
                }
            }

            resultMap.put("originalFilename", originalFilename);

            return R.ok(resultMap);
        } catch (IOException e) {
            log.error("处理上传文件失败: {}", originalFilename, e);
            return R.warning("处理上传文件失败: " + e.getMessage());
        }
    }

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
            log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

            if (StrUtil.isEmpty(markdownContent)) {
                return R.warning("文件内容为空");
            }

            JSONObject result = aiService.callAi(markdownContent);

            if (result == null) {
                return R.warning("AI解析失败，未能获取结果");
            }

            Map<String, Object> resultMap = new HashMap<>();
            for (String key : result.keySet()) {
                Object value = result.get(key);
                if (value instanceof cn.hutool.json.JSONNull) {
                    resultMap.put(key, null);
                } else {
                    resultMap.put(key, value);
                }
            }

            resultMap.put("originalFilename", originalFilename);

            return R.ok(resultMap);
        } catch (IOException e) {
            log.error("处理上传文件失败: {}", originalFilename, e);
            return R.warning("处理上传文件失败: " + e.getMessage());
        }
    }
}
