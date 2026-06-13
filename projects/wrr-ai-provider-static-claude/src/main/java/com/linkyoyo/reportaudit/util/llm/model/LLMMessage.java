package com.linkyoyo.reportaudit.util.llm.model;

/**
 * LLM消息结构
 * 
 * @author AI Assistant
 * @date 2025-01-13
 */
public class LLMMessage {
    
    private String role;    // system, user, assistant
    private String content;
    
    public LLMMessage() {}
    
    public LLMMessage(String role, String content) {
        this.role = role;
        this.content = content;
    }
    
    /**
     * 创建系统消息
     */
    public static LLMMessage system(String content) {
        return new LLMMessage("system", content);
    }
    
    /**
     * 创建用户消息
     */
    public static LLMMessage user(String content) {
        return new LLMMessage("user", content);
    }
    
    /**
     * 创建助手消息
     */
    public static LLMMessage assistant(String content) {
        return new LLMMessage("assistant", content);
    }
    
    // Getters and Setters
    public String getRole() {
        return role;
    }
    
    public void setRole(String role) {
        this.role = role;
    }
    
    public String getContent() {
        return content;
    }
    
    public void setContent(String content) {
        this.content = content;
    }
    
    @Override
    public String toString() {
        return "LLMMessage{" +
                "role='" + role + '\'' +
                ", content='" + content + '\'' +
                '}';
    }
}
