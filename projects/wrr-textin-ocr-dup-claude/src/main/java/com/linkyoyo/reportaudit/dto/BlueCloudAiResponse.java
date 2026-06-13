package com.linkyoyo.reportaudit.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class BlueCloudAiResponse {
    private String id;
    private String name;
    private Long size;
    private String extension;
    private String mime_type;
    private String description;
    private String created_by;
    private Long created_at;
}
