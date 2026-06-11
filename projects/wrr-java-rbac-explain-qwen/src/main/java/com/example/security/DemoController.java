package com.example.security;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 演示控制器 —— 展示 @PreAuthorize 注解与 RBAC 服务的集成
 *
 * 权限注解生效依赖 SecurityConfig 中的 @EnableGlobalMethodSecurity(prePostEnabled=true)
 */
@RestController
@RequestMapping("/api")
public class DemoController {

    private final RbacService rbacService;

    public DemoController(RbacService rbacService) {
        this.rbacService = rbacService;
    }

    /** 所有已认证用户均可访问 */
    @GetMapping("/data/view")
    @PreAuthorize("isAuthenticated()")
    public Map<String, String> viewData() {
        return Map.of("message", "这是公开数据，所有登录用户可见");
    }

    /** 需要 system:manage 权限 —— 仅 SUPER_ADMIN */
    @PostMapping("/system/manage")
    @PreAuthorize("@rbacService.hasPermission(authentication.name, 'system:manage')")
    public Map<String, String> manageSystem() {
        return Map.of("message", "系统管理操作执行成功");
    }

    /** 需要 user:manage 权限 —— SUPER_ADMIN 和 ADMIN（通过继承） */
    @PostMapping("/user/manage")
    @PreAuthorize("@rbacService.hasPermission(authentication.name, 'user:manage')")
    public Map<String, String> manageUser(@RequestParam String targetUser) {
        return Map.of("message", "用户 " + targetUser + " 管理操作执行成功");
    }

    /** 需要 log:view 权限 —— SUPER_ADMIN / ADMIN / USER（通过继承链） */
    @GetMapping("/log/view")
    @PreAuthorize("@rbacService.hasPermission(authentication.name, 'log:view')")
    public Map<String, String> viewLogs() {
        return Map.of("message", "日志数据：...");
    }

    /** 需要 data:export 权限 —— 仅 SUPER_ADMIN 和 ADMIN */
    @GetMapping("/data/export")
    @PreAuthorize("@rbacService.hasPermission(authentication.name, 'data:export')")
    public Map<String, String> exportData() {
        return Map.of("message", "数据导出完成");
    }

    /** 健康检查 —— 公开接口，无需认证 */
    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "UP");
    }
}
