package com.linkyoyo.reportaudit.config;

import com.linkyoyo.reportaudit.websocket.TaskProgressWebSocketHandler;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.*;
import org.springframework.http.server.*;
import org.springframework.web.socket.WebSocketHandler;
import java.util.Map;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {
    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(new TaskProgressWebSocketHandler(), "/ws/task-progress/**")
            .addInterceptors(new HandshakeInterceptor() {
                @Override
                public boolean beforeHandshake(ServerHttpRequest req, ServerHttpResponse resp, WebSocketHandler h, Map<String, Object> attrs) {
                    String origin = req.getHeaders().getOrigin();
                    return origin != null;
                }
                @Override
                public void afterHandshake(ServerHttpRequest req, ServerHttpResponse resp, WebSocketHandler h, Exception ex) {}
            })
            .setAllowedOrigins("*");
    }
}
