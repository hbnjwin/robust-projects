package com.example.security;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.stereotype.Service;

import javax.annotation.PostConstruct;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * RBAC 权限服务
 *
 * 角色继承规则（父角色权限 >= 子角色权限）：
 *   SUPER_ADMIN -> ADMIN -> USER -> GUEST
 *   子角色自动继承所有祖先角色的权限，因此子角色权限集合是父角色的超集。
 *   例：USER 拥有 GUEST 的全部权限 + 自身独有权限。
 *
 * 缓存策略：
 *   - 用户最终权限使用 Caffeine 本地缓存，key = userId
 *   - 角色 / 权限 / 继承关系变更时主动清除缓存，保证一致性
 */
@Service
@EnableCaching
public class RbacService {

    // ==================== 数据模型 ====================

    /** 角色 -> 该角色直接拥有的权限集合 */
    private final Map<String, Set<String>> rolePermissions = new ConcurrentHashMap<>();

    /** 用户 -> 该用户直接拥有的角色集合 */
    private final Map<String, Set<String>> userRoles = new ConcurrentHashMap<>();

    /**
     * 角色继承关系：childRole -> Set<parentRoles>
     * 父角色权限更大，子角色继承父角色的所有权限。
     * 例：ADMIN -> {SUPER_ADMIN}  表示 ADMIN 继承 SUPER_ADMIN 的权限
     */
    private final Map<String, Set<String>> roleHierarchy = new ConcurrentHashMap<>();

    // ==================== 权限缓存 ====================

    /**
     * 用户最终有效权限缓存：userId -> Set<permission>
     * 使用 Caffeine 本地缓存，最大 10000 条，写入后 30 分钟过期。
     * 角色/权限变更时通过 {@link #evictPermissionCache()} 主动失效。
     */
    private final Cache<String, Set<String>> permissionCache = Caffeine.newBuilder()
            .maximumSize(10_000)
            .expireAfterWrite(30, TimeUnit.MINUTES)
            .build();

    // ==================== 初始化演示数据 ====================

    @PostConstruct
    public void init() {
        // --- 角色权限定义（父角色权限 >= 子角色） ---
        rolePermissions.put("SUPER_ADMIN", new HashSet<>(Arrays.asList(
                "system:manage", "user:manage", "role:manage", "log:view", "data:export"
        )));
        rolePermissions.put("ADMIN", new HashSet<>(Arrays.asList(
                "user:manage", "log:view", "data:export"
        )));
        rolePermissions.put("USER", new HashSet<>(Arrays.asList(
                "log:view", "data:view"
        )));
        rolePermissions.put("GUEST", new HashSet<>(Arrays.asList(
                "data:view"
        )));

        // --- 角色继承关系：child -> parents ---
        // SUPER_ADMIN 是最高角色，没有父角色
        roleHierarchy.put("ADMIN", new HashSet<>(Collections.singletonList("SUPER_ADMIN")));
        roleHierarchy.put("USER", new HashSet<>(Collections.singletonList("ADMIN")));
        roleHierarchy.put("GUEST", new HashSet<>(Collections.singletonList("USER")));

        // --- 用户角色分配 ---
        userRoles.put("alice", new HashSet<>(Collections.singletonList("SUPER_ADMIN")));
        userRoles.put("bob", new HashSet<>(Collections.singletonList("ADMIN")));
        userRoles.put("carol", new HashSet<>(Collections.singletonList("USER")));
        userRoles.put("dave", new HashSet<>(Collections.singletonList("GUEST")));
    }

    // ==================== 核心权限判断 ====================

    /**
     * 判断用户是否拥有指定权限（带缓存）。
     * 先查缓存，未命中时计算完整权限集（含继承）后写入缓存。
     */
    public boolean hasPermission(String userId, String permission) {
        Set<String> effectivePerms = permissionCache.get(userId, this::computeEffectivePermissions);
        return effectivePerms != null && effectivePerms.contains(permission);
    }

    /**
     * 获取用户的全部有效权限（含角色继承），优先从缓存读取。
     */
    public Set<String> getEffectivePermissions(String userId) {
        return permissionCache.get(userId, this::computeEffectivePermissions);
    }

    /**
     * 计算用户的完整有效权限集：
     * 1. 获取用户所有角色
     * 2. 对每个角色，沿继承链向上收集所有祖先角色的权限
     * 3. 合并去重后返回
     */
    private Set<String> computeEffectivePermissions(String userId) {
        Set<String> roles = userRoles.getOrDefault(userId, Collections.emptySet());
        Set<String> allPermissions = new HashSet<>();

        for (String role : roles) {
            // 收集该角色自身及其所有祖先角色的权限
            collectPermissionsRecursive(role, allPermissions, new HashSet<>());
        }

        return Collections.unmodifiableSet(allPermissions);
    }

    /**
     * 递归收集角色权限：先加自身权限，再沿 parentRoles 向上遍历。
     * 使用 visited 防止循环继承导致死循环。
     */
    private void collectPermissionsRecursive(String role, Set<String> permissions, Set<String> visited) {
        if (!visited.add(role)) {
            return; // 已访问过，防止循环
        }
        // 加入该角色自身的权限
        Set<String> directPerms = rolePermissions.getOrDefault(role, Collections.emptySet());
        permissions.addAll(directPerms);

        // 递归加入父角色的权限（父角色权限更大，子角色继承父角色）
        Set<String> parents = roleHierarchy.getOrDefault(role, Collections.emptySet());
        for (String parent : parents) {
            collectPermissionsRecursive(parent, permissions, visited);
        }
    }

    // ==================== 角色继承关系修复后的正确性验证 ====================
    //
    // 修复前 bug：checkParentRoles() 直接 return false，继承关系完全无效。
    //            导致子角色只有自身直接权限，可能出现"子角色权限 < 父角色"的反转。
    //
    // 修复后：collectPermissionsRecursive() 沿 roleHierarchy 向上递归，
    //        子角色自动获得所有祖先角色的权限，保证：
    //        effectivePermissions(child) ⊇ effectivePermissions(parent)
    //
    // 例：GUEST 继承 USER 继承 ADMIN 继承 SUPER_ADMIN
    //     GUEST 的有效权限 = GUEST自身 + USER + ADMIN + SUPER_ADMIN 的全部权限

    // ==================== 管理操作（变更时清除缓存保证一致性）====================

    /**
     * 为用户分配角色，并清除该用户的权限缓存。
     */
    public void assignRole(String userId, String role) {
        userRoles.computeIfAbsent(userId, k -> new HashSet<>()).add(role);
        permissionCache.invalidate(userId);
    }

    /**
     * 移除用户角色，并清除该用户的权限缓存。
     */
    public void revokeRole(String userId, String role) {
        Set<String> roles = userRoles.get(userId);
        if (roles != null) {
            roles.remove(role);
        }
        permissionCache.invalidate(userId);
    }

    /**
     * 为角色添加权限，并清除所有受该角色影响的用户缓存。
     */
    public void addPermission(String role, String permission) {
        rolePermissions.computeIfAbsent(role, k -> new HashSet<>()).add(permission);
        evictAffectedUsers(role);
    }

    /**
     * 移除角色的权限，并清除所有受该角色影响的用户缓存。
     */
    public void removePermission(String role, String permission) {
        Set<String> perms = rolePermissions.get(role);
        if (perms != null) {
            perms.remove(permission);
        }
        evictAffectedUsers(role);
    }

    /**
     * 设置角色继承关系（child 继承 parent），并清除全局缓存。
     */
    public void setRoleHierarchy(String childRole, String parentRole) {
        roleHierarchy.computeIfAbsent(childRole, k -> new HashSet<>()).add(parentRole);
        // 继承关系变更影响范围大，清除全部缓存
        permissionCache.invalidateAll();
    }

    /**
     * 清除全部权限缓存（角色/权限/继承关系批量变更时调用）。
     */
    public void evictPermissionCache() {
        permissionCache.invalidateAll();
    }

    /**
     * 清除拥有指定角色（及其子角色）的所有用户的缓存。
     * 因为角色权限变更后，所有继承该角色的子角色用户的有效权限都会变化。
     */
    private void evictAffectedUsers(String changedRole) {
        // 收集所有直接或间接受影响的角色（changedRole 本身 + 所有以它为祖先的角色）
        Set<String> affectedRoles = new HashSet<>();
        collectChildRoles(changedRole, affectedRoles);

        // 清除拥有这些角色的用户的缓存
        for (Map.Entry<String, Set<String>> entry : userRoles.entrySet()) {
            if (!Collections.disjoint(entry.getValue(), affectedRoles)) {
                permissionCache.invalidate(entry.getKey());
            }
        }
    }

    /**
     * 反向收集子角色：找到所有以 targetRole 为祖先的角色。
     * 用于精确清除受角色权限变更影响的用户缓存。
     */
    private void collectChildRoles(String targetRole, Set<String> result) {
        result.add(targetRole);
        for (Map.Entry<String, Set<String>> entry : roleHierarchy.entrySet()) {
            if (entry.getValue().contains(targetRole) && result.add(entry.getKey())) {
                collectChildRoles(entry.getKey(), result);
            }
        }
    }
}
