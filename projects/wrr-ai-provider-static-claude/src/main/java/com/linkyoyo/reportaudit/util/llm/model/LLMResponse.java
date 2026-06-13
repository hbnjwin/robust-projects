package com.linkyoyo.reportaudit.util.llm.model;

import java.util.Map;

public class LLMResponse {

    private String content;
    private Map<String, Object> usage;
    private String model;
    private String provider;
    private boolean success;
    private String error;

    public LLMResponse() { this.success = true; }

    public LLMResponse(String content) {
        this.content = content;
        this.success = true;
    }

    public LLMResponse(String content, boolean success, String error) {
        this.content = content;
        this.success = success;
        this.error = error;
    }

    public static LLMResponse success(String content) {
        return new LLMResponse(content, true, null);
    }

    public static LLMResponse success(String content, String model, String provider, Map<String, Object> usage) {
        LLMResponse response = new LLMResponse(content, true, null);
        response.setModel(model);
        response.setProvider(provider);
        response.setUsage(usage);
        return response;
    }

    public static LLMResponse error(String error) {
        return new LLMResponse("", false, error);
    }

    public static LLMResponse error(String error, String provider) {
        LLMResponse response = new LLMResponse("", false, error);
        response.setProvider(provider);
        return response;
    }

    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
    public Map<String, Object> getUsage() { return usage; }
    public void setUsage(Map<String, Object> usage) { this.usage = usage; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public String getProvider() { return provider; }
    public void setProvider(String provider) { this.provider = provider; }
    public boolean isSuccess() { return success; }
    public void setSuccess(boolean success) { this.success = success; }
    public String getError() { return error; }
    public void setError(String error) { this.error = error; }

    @Override
    public String toString() {
        return "LLMResponse{content='" + content + "', model='" + model +
                "', provider='" + provider + "', success=" + success +
                ", error='" + error + "'}";
    }
}
