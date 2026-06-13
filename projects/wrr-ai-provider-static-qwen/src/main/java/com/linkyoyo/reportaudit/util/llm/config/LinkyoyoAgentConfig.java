package com.linkyoyo.reportaudit.util.llm.config;

/**
 * Linkyoyo Agent配置
 */
public class LinkyoyoAgentConfig extends LLMConfig {

    private String token;
    private String url;

    public String getToken() {
        return token;
    }

    public void setToken(String token) {
        this.token = token;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    @Override
    public boolean isValid() {
        return url != null && !url.isEmpty()
                && token != null && !token.isEmpty();
    }
}
