package com.linkyoyo.reportaudit.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class BlueCloudAiMarkdownResponse {
    private Integer code;
    private Data data;
    
    @lombok.Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class Data {
        private String id;
        private String markdown_content;
    }
}
