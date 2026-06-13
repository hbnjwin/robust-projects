package com.linkyoyo.reportaudit.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * Blue Cloud AI 配置常量
 */
@Configuration
public class BlueCloudAiConfig {
    // API URLs - Injected from properties or defaults
    @Value("${bluecloud.ai.upload-api-url:}")
    private String uploadApiUrl;

    @Value("${bluecloud.ai.markdown-api-url:}")
    private String markdownApiUrl;

    // Auth Token - MUST be provided via external configuration (application.yml or env variable)
    @Value("${bluecloud.ai.auth-token:}")
    private String authToken;

    // Provider settings - Injected from properties or defaults
    @Value("${bluecloud.ai.provider.name:textin}")
    private String providerName;

    @Value("${bluecloud.ai.model.name:gpt-4o-5}")
    private String modelName;

    @Value("${bluecloud.ai.temperature:0.7}")
    private double temperature;

    @Value("${bluecloud.ai.query:请解析文件为markdown格式内容}")
    private String query;

    public String getProviderName() {
        return providerName;
    }

    public String getModelName() {
        return modelName;
    }

    public double getTemperature() {
        return temperature;
    }

    public String getQuery() {
        return query;
    }

    // Getters for API URLs and Auth Token
    public String getUploadApiUrl() {
        return uploadApiUrl;
    }

    public String getMarkdownApiUrl() {
        return markdownApiUrl;
    }

    public String getAuthToken() {
        return authToken;
    }
}
