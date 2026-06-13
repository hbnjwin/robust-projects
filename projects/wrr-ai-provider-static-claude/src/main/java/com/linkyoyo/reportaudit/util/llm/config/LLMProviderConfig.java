package com.linkyoyo.reportaudit.util.llm.config;

public class LLMProviderConfig {

    private LLMProviderType type;
    private String url;
    private String key;
    private String model;
    private String apiVersion;
    private String prompt;
    private boolean isAzure;
    private float temperature = 0.1f;
    private int maxTokens = 4096;

    public LLMProviderConfig() {}

    public LLMProviderConfig(LLMProviderType type, String url, String key, String model) {
        this.type = type;
        this.url = url;
        this.key = key;
        this.model = model;
    }

    public String buildAzureEndpointUrl() {
        if (type != LLMProviderType.AZURE_OPENAI) {
            return url;
        }
        String base = url.endsWith("/") ? url : url + "/";
        return base + "openai/deployments/" + model + "/chat/completions?api-version=" + apiVersion;
    }

    public boolean isValid() {
        return type != null && url != null && !url.isEmpty()
                && key != null && !key.isEmpty();
    }

    public LLMProviderType getType() { return type; }
    public void setType(LLMProviderType type) { this.type = type; }
    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
    public String getKey() { return key; }
    public void setKey(String key) { this.key = key; }
    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public String getApiVersion() { return apiVersion; }
    public void setApiVersion(String apiVersion) { this.apiVersion = apiVersion; }
    public String getPrompt() { return prompt; }
    public void setPrompt(String prompt) { this.prompt = prompt; }
    public boolean isAzure() { return isAzure; }
    public void setAzure(boolean azure) { isAzure = azure; }
    public float getTemperature() { return temperature; }
    public void setTemperature(float temperature) { this.temperature = temperature; }
    public int getMaxTokens() { return maxTokens; }
    public void setMaxTokens(int maxTokens) { this.maxTokens = maxTokens; }
}
