package com.linkyoyo.reportaudit.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "textin")
public class TextinConfig {
    private String appId;
    private String secretCode;
    private String apiUrl;
}
