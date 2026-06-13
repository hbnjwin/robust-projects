package com.linkyoyo.reportaudit.util.llm.http;

import com.linkyoyo.reportaudit.config.AiServiceConfig;
import lombok.extern.slf4j.Slf4j;
import okhttp3.OkHttpClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.annotation.PostConstruct;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.util.concurrent.TimeUnit;

/**
 * Secure HTTP client factory.
 * Single source of truth for SSL trust-all config and OkHttpClient instance,
 * eliminating duplication between CommonFunc.createSecureHttpClient() and DynamicLLMService.initHttpClient().
 */
@Component
@Slf4j
public class SecureHttpClientFactory {

    private final AiServiceConfig serviceConfig;
    private volatile OkHttpClient sharedClient;

    @Autowired
    public SecureHttpClientFactory(AiServiceConfig serviceConfig) {
        this.serviceConfig = serviceConfig;
    }

    @PostConstruct
    public void init() {
        this.sharedClient = createClient();
    }

    public OkHttpClient getClient() {
        return sharedClient;
    }

    private OkHttpClient createClient() {
        try {
            final TrustManager[] trustAllCerts = new TrustManager[]{
                new X509TrustManager() {
                    @Override
                    public void checkClientTrusted(java.security.cert.X509Certificate[] chain, String authType) {}

                    @Override
                    public void checkServerTrusted(java.security.cert.X509Certificate[] chain, String authType) {}

                    @Override
                    public java.security.cert.X509Certificate[] getAcceptedIssuers() {
                        return new java.security.cert.X509Certificate[]{};
                    }
                }
            };

            final SSLContext sslContext = SSLContext.getInstance("SSL");
            sslContext.init(null, trustAllCerts, new java.security.SecureRandom());

            long connectTimeoutMs = serviceConfig.getConnectTimeout();
            long readTimeoutMs = serviceConfig.getReadTimeout();
            long writeTimeoutMs = serviceConfig.getWriteTimeout();

            OkHttpClient client = new OkHttpClient.Builder()
                    .sslSocketFactory(sslContext.getSocketFactory(), (X509TrustManager) trustAllCerts[0])
                    .hostnameVerifier((hostname, session) -> true)
                    .connectTimeout(connectTimeoutMs, TimeUnit.MILLISECONDS)
                    .readTimeout(readTimeoutMs, TimeUnit.MILLISECONDS)
                    .writeTimeout(writeTimeoutMs, TimeUnit.MILLISECONDS)
                    .build();

            log.info("SecureHttpClient initialized: connectTimeout={}ms, readTimeout={}ms, writeTimeout={}ms",
                    connectTimeoutMs, readTimeoutMs, writeTimeoutMs);
            return client;

        } catch (Exception e) {
            log.error("SSL client init failed, using default: {}", e.getMessage(), e);
            return new OkHttpClient.Builder()
                    .connectTimeout(60, TimeUnit.SECONDS)
                    .readTimeout(120, TimeUnit.SECONDS)
                    .writeTimeout(60, TimeUnit.SECONDS)
                    .build();
        }
    }
}
