package com.linkyoyo.reportaudit.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

/**
 * Linkyoyo AI Agent 配置
 * 上传 / 聊天 URL 和认证令牌通过外部配置注入，不在代码中硬编码。
 */
@Configuration
public class LinkyoyoAiConfig {

    @Value("${linkyoyo.ai.url:}")
    private String url;

    @Value("${linkyoyo.ai.token:}")
    private String token;

    public String getUrl() {
        return url;
    }

    public String getToken() {
        return token;
    }
}
