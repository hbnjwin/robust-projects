package com.example.classroom;

import jakarta.websocket.Session;
import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class SessionInfo {
    private Session session;
    private String classId;
    private String userId;
    private long lastActiveTime;
}
