package com.linkyoyo.reportaudit.websocket;

import org.springframework.web.socket.*;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import java.util.*;

public class TaskProgressWebSocketHandler extends TextWebSocketHandler {
    private final Map<String, WebSocketSession> sessions = new HashMap<>();

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.put(session.getId(), session);
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session.getId());
    }

    public void broadcastProgress(String taskId, int current, int total) {
        String msg = String.format("{\"taskId\":\"%s\",\"current\":%d,\"total\":%d}", taskId, current, total);
        for (WebSocketSession s : sessions.values()) {
            try { s.sendMessage(new TextMessage(msg)); } catch (Exception e) {}
        }
    }
}
