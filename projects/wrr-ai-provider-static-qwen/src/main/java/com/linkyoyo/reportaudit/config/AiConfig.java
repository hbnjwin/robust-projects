package com.linkyoyo.reportaudit.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * AI 配置类
 */
@Configuration
public class AiConfig {
    @Value("${link-yo-yo.ai.isAzure:true}")
    private boolean isAzure;
    
    @Value("${link-yo-yo.ai.url:https://subs1-5.openai.azure.com/}")
    private String url;
    
    @Value("${link-yo-yo.ai.key:REDACTED_AZURE_OPENAI_KEY_2}")
    private String key;
    
    @Value("${link-yo-yo.ai.model:gpt-4o-5}")
    private String model;
    
    @Value("${link-yo-yo.ai.version:2024-05-01-preview}")
    private String version;
    
    @Value("${link-yo-yo.ai.prompt:解析内容：标准类型（国标   ||   行业标准 ||  企业标准/地方标准）,标准号,标准中文名,标准英文名，发布日期,实施日期,标准状态,发布单位,提出单位,起草单位,起草人,范围,规范性引用文件,**前言,引言,术语和定义,参考文献**;以json格式输出}")
    private String prompt;
    
    @Value("${link-yo-yo.ai.deepseek.isAzure:false}")
    private boolean deepseekIsAzure;
    
    @Value("${link-yo-yo.ai.deepseek.url:https://DeepSeek-R1-ucuty.eastus.models.ai.azure.com}")
    private String deepseekUrl;
    
    @Value("${link-yo-yo.ai.deepseek.key:REDACTED_DEEPSEEK_API_KEY}")
    private String deepseekKey;
    
    @Value("${link-yo-yo.ai.deepseek.model:DeepSeek-R1-ucuty}")
    private String deepseekModel;
    
    @Value("${link-yo-yo.ai.deepseek.prompt:解析内容：标准类型（国标   ||   行业标准 ||  企业标准/地方标准）,标准号,标准中文名,标准英文名，发布日期,实施日期,标准状态,发布单位,提出单位,起草单位,起草人,范围,规范性引用文件,**前言,引言,术语和定义,参考文献**;以json格式输出}")
    private String deepseekPrompt;

    public boolean isAzure() {
        return isAzure;
    }

    public String getUrl() {
        return url;
    }

    public String getKey() {
        return key;
    }

    public String getModel() {
        return model;
    }

    public String getVersion() {
        return version;
    }

    public String getPrompt() {
        return prompt;
    }

    public boolean isDeepseekIsAzure() {
        return deepseekIsAzure;
    }

    public String getDeepseekUrl() {
        return deepseekUrl;
    }

    public String getDeepseekKey() {
        return deepseekKey;
    }

    public String getDeepseekModel() {
        return deepseekModel;
    }

    public String getDeepseekPrompt() {
        return deepseekPrompt;
    }
}
