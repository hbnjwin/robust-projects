package com.linkyoyo.reportaudit.util.llm.model;

public class LLMMessage {

    private String role;
    private String content;

    public LLMMessage() {}

    public LLMMessage(String role, String content) {
        this.role = role;
        this.content = content;
    }

    public static LLMMessage system(String content) {
        return new LLMMessage("system", content);
    }

    public static LLMMessage user(String content) {
        return new LLMMessage("user", content);
    }

    public static LLMMessage assistant(String content) {
        return new LLMMessage("assistant", content);
    }

    public String getRole() { return role; }
    public void setRole(String role) { this.role = role; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }

    @Override
    public String toString() {
        return "LLMMessage{role='" + role + "', content='" + content + "'}";
    }
}
