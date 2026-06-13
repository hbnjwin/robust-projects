package com.linkyoyo.reportaudit.service.impl;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.config.AiConfig;
import com.linkyoyo.reportaudit.service.AiService;
import com.linkyoyo.reportaudit.support.CommonFunc;
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
        log.info("调用Azure AI，内容长度: {}", content.length());
        log.info("当前Azure配置 - URL: {}, Model: {}, Version: {}", aiConfig.getUrl(), aiConfig.getModel(), aiConfig.getVersion());

        String sanitized = sanitizeContent(content);
        log.info("处理后的内容长度: {}", sanitized.length());

        JSONObject result = CommonFunc.callAiWithOkHttp(sanitized);
        return toResultMap(result);
    }

    @Override
    public Map<String, Object> callDeepSeekAi(String content) {
        log.info("调用DeepSeek AI，内容长度: {}", content.length());
        log.info("当前DeepSeek配置 - URL: {}, Model: {}", aiConfig.getDeepseekUrl(), aiConfig.getDeepseekModel());

        String sanitized = sanitizeContent(content);
        log.info("处理后的内容长度: {}", sanitized.length());

        JSONObject result = CommonFunc.callDeepSeekAi(sanitized);
        return toResultMap(result);
    }

    @Override
    public Map<String, Object> uploadAndAnalyzeMd(String markdownContent, String originalFilename, boolean useDeepSeek) {
        log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

        JSONObject result;
        if (useDeepSeek) {
            log.info("使用DeepSeek AI解析Markdown文件: {}", originalFilename);
            result = CommonFunc.callDeepSeekAi(markdownContent);
        } else {
            log.info("使用Azure AI解析Markdown文件: {}", originalFilename);
            result = CommonFunc.callAiWithOkHttp(markdownContent);
        }

        Map<String, Object> resultMap = toResultMap(result);
        resultMap.put("originalFilename", originalFilename);
        return resultMap;
    }

    @Override
    public Map<String, Object> uploadMdToCallAi(String markdownContent, String originalFilename) {
        log.info("读取上传的Markdown文件内容: {}, 大小: {} 字节", originalFilename, markdownContent.length());

        if (StrUtil.isEmpty(markdownContent)) {
            throw new IllegalArgumentException("文件内容为空");
        }

        JSONObject result = commonFunc.callAi(markdownContent);

        if (result == null) {
            throw new RuntimeException("AI解析失败，未能获取结果");
        }

        Map<String, Object> resultMap = toResultMap(result);
        resultMap.put("originalFilename", originalFilename);
        return resultMap;
    }

    /**
     * 处理内容中的特殊字符：删除控制字符，转义反斜杠和引号
     */
    private String sanitizeContent(String content) {
        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");
        return content;
    }

    /**
     * 将Hutool JSONObject转换为Java Map对象，解决序列化问题。
     * 当结果包含error键时，抛出RuntimeException。
     */
    private Map<String, Object> toResultMap(JSONObject result) {
        if (result.containsKey("error")) {
            String errorMsg = result.getStr("error");
            log.error("AI调用失败: {}", errorMsg);
            throw new RuntimeException(errorMsg);
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
        return resultMap;
    }
}
