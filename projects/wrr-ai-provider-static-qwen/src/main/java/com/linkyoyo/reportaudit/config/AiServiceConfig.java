package com.linkyoyo.reportaudit.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * AI服务配置类
 * 管理重试、超时等参数
 */
@Configuration
@ConfigurationProperties(prefix = "ai.service")
public class AiServiceConfig {

    /**
     * 最大重试次数
     */
    private int maxRetries = 3;

    /**
     * 基础重试延迟（毫秒）
     */
    private int baseRetryDelay = 2000;

    /**
     * 连接超时（毫秒）
     */
    private int connectTimeout = 15000;

    /**
     * 读取超时（毫秒）
     */
    private int readTimeout = 120000;

    /**
     * 是否启用重试机制
     */
    private boolean retryEnabled = true;

    /**
     * 是否启用递增延迟
     */
    private boolean exponentialBackoff = true;

    /**
     * 最大重试延迟（毫秒）
     */
    private int maxRetryDelay = 30000;

    /**
     * AI服务响应超时阈值（毫秒）
     * 超过此时间会记录警告日志
     */
    private int slowResponseThreshold = 10000;

    // Getters and Setters
    public int getMaxRetries() {
        return maxRetries;
    }

    public void setMaxRetries(int maxRetries) {
        this.maxRetries = maxRetries;
    }

    public int getBaseRetryDelay() {
        return baseRetryDelay;
    }

    public void setBaseRetryDelay(int baseRetryDelay) {
        this.baseRetryDelay = baseRetryDelay;
    }

    public int getConnectTimeout() {
        return connectTimeout;
    }

    public void setConnectTimeout(int connectTimeout) {
        this.connectTimeout = connectTimeout;
    }

    public int getReadTimeout() {
        return readTimeout;
    }

    public void setReadTimeout(int readTimeout) {
        this.readTimeout = readTimeout;
    }

    public boolean isRetryEnabled() {
        return retryEnabled;
    }

    public void setRetryEnabled(boolean retryEnabled) {
        this.retryEnabled = retryEnabled;
    }

    public boolean isExponentialBackoff() {
        return exponentialBackoff;
    }

    public void setExponentialBackoff(boolean exponentialBackoff) {
        this.exponentialBackoff = exponentialBackoff;
    }

    public int getMaxRetryDelay() {
        return maxRetryDelay;
    }

    public void setMaxRetryDelay(int maxRetryDelay) {
        this.maxRetryDelay = maxRetryDelay;
    }

    public int getSlowResponseThreshold() {
        return slowResponseThreshold;
    }

    public void setSlowResponseThreshold(int slowResponseThreshold) {
        this.slowResponseThreshold = slowResponseThreshold;
    }

    /**
     * 计算重试延迟时间
     */
    public int calculateRetryDelay(int attempt) {
        if (!exponentialBackoff) {
            return baseRetryDelay;
        }
        
        // 指数退避算法：baseDelay * 2^(attempt-1)
        int delay = baseRetryDelay * (int) Math.pow(2, attempt - 1);
        return Math.min(delay, maxRetryDelay);
    }

    /**
     * 检查响应时间是否过慢
     */
    public boolean isSlowResponse(long responseTime) {
        return responseTime > slowResponseThreshold;
    }
}
