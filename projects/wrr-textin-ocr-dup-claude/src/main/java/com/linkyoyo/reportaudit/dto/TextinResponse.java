package com.linkyoyo.reportaudit.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class TextinResponse {
    private Integer duration;
    private String message;
    private TextinResult result;

    @Data
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class TextinResult {
        private String markdown;
        private Integer success_count;
        private Integer pages;
        // Other fields can be added as needed
    }
}
