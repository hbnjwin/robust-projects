package com.linkyoyo.reportaudit.util.llm.config;

/**
 * Linkyoyo Agent配置类
 * 
 * @author AI Assistant
 * @date 2025-01-13
 */
public class LinkyoyoAgentConfig extends LLMConfig {
    
    private String token;
    
    public LinkyoyoAgentConfig() {
        super();
    }
    
    public LinkyoyoAgentConfig(String url, String token, String model, String authType, 
                              Float temperature, Integer maxTokens) {
        super(url, model, authType, temperature, maxTokens);
        this.token = token;
    }
    
    public String getToken() {
        return token;
    }
    
    public void setToken(String token) {
        this.token = token;
    }
    
    /**
     * 验证配置是否完整
     */
    public boolean isValid() {
        boolean urlValid = url != null && !url.trim().isEmpty();
        boolean tokenValid = token != null && !token.trim().isEmpty();
        boolean modelValid = model != null && !model.trim().isEmpty();
        
        if (!urlValid || !tokenValid || !modelValid) {
            System.out.println("LinkyoyoAgentConfig验证失败: url=" + urlValid + 
                             ", token=" + tokenValid + ", model=" + modelValid);
            System.out.println("实际值: url=" + url + ", token=" + (token != null ? "***" : "null") + 
                             ", model=" + model);
        }
        
        return urlValid && tokenValid && modelValid;
    }
}
