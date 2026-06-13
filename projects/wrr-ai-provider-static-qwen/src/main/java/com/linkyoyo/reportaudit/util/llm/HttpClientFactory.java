package com.linkyoyo.reportaudit.util.llm;

import com.linkyoyo.reportaudit.config.AiServiceConfig;
import lombok.extern.slf4j.Slf4j;
import okhttp3.OkHttpClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.security.cert.X509Certificate;
import java.util.concurrent.TimeUnit;

/**
 * HTTP客户端工厂
 * 统一SSL trust-all配置和超时设置，消除CommonFunc和DynamicLLMService中的重复代码
 */
@Component
@Slf4j
public class HttpClientFactory {

    @Autowired(required = false)
    private AiServiceConfig aiServiceConfig;

    private volatile OkHttpClient sharedClient;

    /**
     * 获取共享的OkHttpClient单例（SSL trust-all + AiServiceConfig超时配置）
     */
    public OkHttpClient getSharedClient() {
        if (sharedClient == null) {
            synchronized (this) {
                if (sharedClient == null) {
                    sharedClient = createClient(
                            getConnectTimeout(),
                            getReadTimeout(),
                            getWriteTimeout()
                    );
                }
            }
        }
        return sharedClient;
    }

    /**
     * 创建自定义超时的OkHttpClient（毫秒）
     */
    public OkHttpClient createClient(int connectTimeoutMs, int readTimeoutMs, int writeTimeoutMs) {
        try {
            final TrustManager[] trustAllCerts = new TrustManager[]{
                new X509TrustManager() {
                    @Override
                    public void checkClientTrusted(X509Certificate[] chain, String authType) {
                    }

                    @Override
                    public void checkServerTrusted(X509Certificate[] chain, String authType) {
                    }

                    @Override
                    public X509Certificate[] getAcceptedIssuers() {
                        return new X509Certificate[]{};
                    }
                }
            };

            final SSLContext sslContext = SSLContext.getInstance("SSL");
            sslContext.init(null, trustAllCerts, new java.security.SecureRandom());

            return new OkHttpClient.Builder()
                    .sslSocketFactory(sslContext.getSocketFactory(), (X509TrustManager) trustAllCerts[0])
                    .hostnameVerifier((hostname, session) -> true)
                    .connectTimeout(connectTimeoutMs, TimeUnit.MILLISECONDS)
                    .readTimeout(readTimeoutMs, TimeUnit.MILLISECONDS)
                    .writeTimeout(writeTimeoutMs, TimeUnit.MILLISECONDS)
                    .build();
        } catch (Exception e) {
            log.error("创建SSL OkHttpClient失败, 回退到默认客户端: {}", e.getMessage(), e);
            return new OkHttpClient.Builder()
                    .connectTimeout(connectTimeoutMs, TimeUnit.MILLISECONDS)
                    .readTimeout(readTimeoutMs, TimeUnit.MILLISECONDS)
                    .writeTimeout(writeTimeoutMs, TimeUnit.MILLISECONDS)
                    .build();
        }
    }

    /**
     * 创建自定义超时的OkHttpClient（秒）
     */
    public OkHttpClient createClientSeconds(int connectSec, int readSec, int writeSec) {
        return createClient(connectSec * 1000, readSec * 1000, writeSec * 1000);
    }

    private int getConnectTimeout() {
        return aiServiceConfig != null ? aiServiceConfig.getConnectTimeout() : 60000;
    }

    private int getReadTimeout() {
        return aiServiceConfig != null ? aiServiceConfig.getReadTimeout() : 120000;
    }

    private int getWriteTimeout() {
        return aiServiceConfig != null ? aiServiceConfig.getWriteTimeout() : 60000;
    }
}
