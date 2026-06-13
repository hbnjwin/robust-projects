package com.linkyoyo.reportaudit.controller;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.support.CommonFunc;
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
    private CommonFunc commonFunc;

    @Value("${paraSet.tempPath:temp}")
    private String tempPath;

    /**
     * 调用Azure OpenAI服务解析内容
     *
     * @param content 需要解析的内容
     * @return 解析结果
     */
    @PostMapping("/azure")
    public R callAzureAi(@RequestBody String content) {
        log.info("接收到Azure AI请求，内容长度: {}", content.length());
        log.info("当前Azure配置 - URL: {}, Model: {}, Version: {}", aiConfig.getUrl(), aiConfig.getModel(), aiConfig.getVersion());

        // 处理内容中的特殊字符
        // 删除控制字符
        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        // 转义反斜杠和引号
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");

        log.info("处理后的内容长度: {}", content.length());

        JSONObject result = CommonFunc.callAiWithOkHttp(content);

        if (result.containsKey("error")) {
            log.error("调用Azure AI失败: {}", result.getStr("error"));
            return R.warning(result.getStr("error"));
        }

        // 将Hutool JSONObject转换为Java Map对象，解决序列化问题
        Map<String, Object> resultMap = new HashMap<>();
        for (String key : result.keySet()) {
            Object value = result.get(key);
            // 处理JSONNull类型
            if (value instanceof cn.hutool.json.JSONNull) {
                resultMap.put(key, null);
            } else {
                resultMap.put(key, value);
            }
        }

        return R.ok(resultMap);
    }

    /**
     * 调用DeepSeek AI服务解析内容
     *
     * @param content 需要解析的内容
     * @return 解析结果
     */
    @PostMapping("/deepseek")
    public R callDeepSeekAi(@RequestBody String content) {
        log.info("接收到DeepSeek AI请求，内容长度: {}", content.length());
        log.info("当前DeepSeek配置 - URL: {}, Model: {}", aiConfig.getDeepseekUrl(), aiConfig.getDeepseekModel());

        // 处理内容中的特殊字符
        // 删除控制字符
        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        // 转义反斜杠和引号
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");

        log.info("处理后的内容长度: {}", content.length());

        JSONObject result = CommonFunc.callDeepSeekAi(content);

        if (result.containsKey("error")) {
            log.error("调用DeepSeek AI失败: {}", result.getStr("error"));
            return R.warning(result.getStr("error"));
        }

        // 将Hutool JSONObject转换为Java Map对象，解决序列化问题
        Map<String, Object> resultMap = new HashMap<>();
        for (String key : result.keySet()) {
            Object value = result.get(key);
            // 处理JSONNull类型
            if (value instanceof cn.hutool.json.JSONNull) {
                resultMap.put(key, null);
            } else {
                resultMap.put(key, value);
            }
        }

        return R.ok(resultMap);
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

        // 检查文件类型
        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || (!originalFilename.endsWith(".md") && !originalFilename.endsWith(".markdown"))) {
            return R.warning("只支持上传Markdown文件(.md或.markdown)");
        }

        try {
            // 直接从MultipartFile获取文件内容
            String markdownContent = new String(file.getBytes());
            log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

            // 根据参数选择使用哪个AI服务
            JSONObject result;
            if (useDeepSeek) {
                log.info("使用DeepSeek AI解析Markdown文件: {}", originalFilename);
                result = CommonFunc.callDeepSeekAi(markdownContent);
            } else {
                log.info("使用Azure AI解析Markdown文件: {}", originalFilename);
                result = CommonFunc.callAiWithOkHttp(markdownContent);
            }

            if (result.containsKey("error")) {
                log.error("AI解析失败: {}", result.getStr("error"));
                return R.warning(result.getStr("error"));
            }

            // 将Hutool JSONObject转换为Java Map对象，解决序列化问题
            Map<String, Object> resultMap = new HashMap<>();
            for (String key : result.keySet()) {
                Object value = result.get(key);
                // 处理JSONNull类型
                if (value instanceof cn.hutool.json.JSONNull) {
                    resultMap.put(key, null);
                } else {
                    resultMap.put(key, value);
                }
            }

            // 添加原始文件名到结果中
            resultMap.put("originalFilename", originalFilename);

            return R.ok(resultMap);
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

        // 检查文件类型
        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || (!originalFilename.endsWith(".md") && !originalFilename.endsWith(".markdown"))) {
            return R.warning("只支持上传Markdown文件(.md或.markdown)");
        }

        try {
            // 读取文件内容
            String markdownContent = new String(file.getBytes());
            log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

            if (StrUtil.isEmpty(markdownContent)) {
                return R.warning("文件内容为空");
            }

            // 调用callAi方法解析内容
            JSONObject result = commonFunc.callAi(markdownContent);

            if (result == null) {
                return R.warning("AI解析失败，未能获取结果");
            }

            // 将Hutool JSONObject转换为Java Map对象，解决序列化问题
            Map<String, Object> resultMap = new HashMap<>();
            for (String key : result.keySet()) {
                Object value = result.get(key);
                // 处理JSONNull类型
                if (value instanceof cn.hutool.json.JSONNull) {
                    resultMap.put(key, null);
                } else {
                    resultMap.put(key, value);
                }
            }

            // 添加原始文件名到结果中
            resultMap.put("originalFilename", originalFilename);

            return R.ok(resultMap);
        } catch (IOException e) {
            log.error("处理上传文件失败: {}", originalFilename, e);
            return R.warning("处理上传文件失败: " + e.getMessage());
        }
    }
}
