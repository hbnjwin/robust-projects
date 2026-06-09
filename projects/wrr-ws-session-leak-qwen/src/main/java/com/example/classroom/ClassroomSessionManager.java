package com.example.classroom;

import jakarta.websocket.*;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import org.springframework.stereotype.Component;
import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;

@ServerEndpoint("/ws/classroom/{classId}/{userId}")
@Component
public class ClassroomSessionManager {

    // BUG: 使用 ConcurrentHashMap 存储所有 WebSocket session
    // 但当学生直接关闭浏览器（而非正常断开）时，onClose 可能不会触发
    // 导致 session 对象一直留在内存中，运行几天后内存持续增长
    private static final ConcurrentHashMap<String, SessionInfo> sessions = new ConcurrentHashMap<>();

    @OnOpen
    public void onOpen(Session session,
                       @PathParam("classId") String classId,
                       @PathParam("userId") String userId) {
        String key = classId + ":" + userId;
        sessions.put(key, new SessionInfo(session, classId, userId, System.currentTimeMillis()));
        broadcastToClass(classId, userId + " 加入了课堂");
    }

    @OnMessage
    public void onMessage(String message, Session session,
                          @PathParam("classId") String classId,
                          @PathParam("userId") String userId) {
        // BUG: 收到消息时没有更新 lastActiveTime
        // 导致即使有心跳也无法正确判断连接是否活跃
        broadcastToClass(classId, userId + ": " + message);
    }

    @OnClose
    public void onClose(@PathParam("classId") String classId,
                        @PathParam("userId") String userId) {
        String key = classId + ":" + userId;
        sessions.remove(key);
        broadcastToClass(classId, userId + " 离开了课堂");
    }

    @OnError
    public void onError(Throwable error,
                        @PathParam("classId") String classId,
                        @PathParam("userId") String userId) {
        // BUG: onError 后没有清理 session
        // 只打了日志，session 还留在 map 里
        System.err.println("WebSocket error for " + userId + ": " + error.getMessage());
    }

    private void broadcastToClass(String classId, String message) {
        sessions.forEach((key, info) -> {
            if (info.getClassId().equals(classId)) {
                try {
                    // BUG: 没有检查 session.isOpen() 就发送消息
                    // 对已关闭的 session 发消息会抛异常
                    info.getSession().getBasicRemote().sendText(message);
                } catch (IOException e) {
                    // BUG: 发送失败后没有清理这个 session
                    System.err.println("发送失败: " + key);
                }
            }
        });
    }

    // BUG: 没有心跳超时清理机制
    // 应该有一个定时任务定期检查 lastActiveTime
    // 超时的 session 主动关闭并从 map 中移除
}
