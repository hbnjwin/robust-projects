package com.linkyoyo.reportaudit.service.impl;

import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.service.AiService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
@Slf4j
public class AiServiceImpl implements AiService {

    @Autowired
    private AiConfig aiConfig;

    @Autowired
    private CommonFunc commonFunc;

    @Override
    public Map<String, Object> callAzureAi(String content) {
        log.info("接收到Azure AI请求，内容长度: {}", content.length());
        log.info("当前Azure配置 - URL: {}, Model: {}, Version: {}", aiConfig.getUrl(), aiConfig.getModel(), aiConfig.getVersion());

        content = sanitizeContent(content);
        log.info("处理后的内容长度: {}", content.length());

        JSONObject result = CommonFunc.callAiWithOkHttp(content);

        if (result.containsKey("error")) {
            log.error("调用Azure AI失败: {}", result.getStr("error"));
            throw new RuntimeException(result.getStr("error"));
        }

        return convertJsonObjectToMap(result);
    }

    @Override
    public Map<String, Object> callDeepSeekAi(String content) {
        log.info("接收到DeepSeek AI请求，内容长度: {}", content.length());
        log.info("当前DeepSeek配置 - URL: {}, Model: {}", aiConfig.getDeepseekUrl(), aiConfig.getDeepseekModel());

        content = sanitizeContent(content);
        log.info("处理后的内容长度: {}", content.length());

        JSONObject result = CommonFunc.callDeepSeekAi(content);

        if (result.containsKey("error")) {
            log.error("调用DeepSeek AI失败: {}", result.getStr("error"));
            throw new RuntimeException(result.getStr("error"));
        }

        return convertJsonObjectToMap(result);
    }

    @Override
    public Map<String, Object> analyzeMarkdown(byte[] fileBytes, String originalFilename, boolean useDeepSeek) {
        String markdownContent = new String(fileBytes);
        log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

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
            throw new RuntimeException(result.getStr("error"));
        }

        Map<String, Object> resultMap = convertJsonObjectToMap(result);
        resultMap.put("originalFilename", originalFilename);
        return resultMap;
    }

    @Override
    public Map<String, Object> analyzeMarkdownWithCallAi(byte[] fileBytes, String originalFilename) {
        String markdownContent = new String(fileBytes);
        log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

        if (markdownContent.isEmpty()) {
            throw new IllegalArgumentException("文件内容为空");
        }

        JSONObject result = commonFunc.callAi(markdownContent);

        if (result == null) {
            throw new RuntimeException("AI解析失败，未能获取结果");
        }

        Map<String, Object> resultMap = convertJsonObjectToMap(result);
        resultMap.put("originalFilename", originalFilename);
        return resultMap;
    }

    /**
     * 清理内容中的特殊字符
     */
    private String sanitizeContent(String content) {
        // 删除控制字符
        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        // 转义反斜杠和引号
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");
        return content;
    }

    /**
     * 将Hutool JSONObject转换为Java Map，处理JSONNull类型
     */
    private Map<String, Object> convertJsonObjectToMap(JSONObject jsonObject) {
        Map<String, Object> resultMap = new HashMap<>();
        for (String key : jsonObject.keySet()) {
            Object value = jsonObject.get(key);
            if (value instanceof cn.hutool.json.JSONNull) {
                resultMap.put(key, null);
            } else {
                resultMap.put(key, value);
            }
        }
        return resultMap;
    }
}
