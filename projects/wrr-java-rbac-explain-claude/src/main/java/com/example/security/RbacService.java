package com.example.security;

import org.springframework.security.access.PermissionEvaluator;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;

import java.io.Serializable;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantReadWriteLock;

@Service
public class RbacService implements PermissionEvaluator {

    // --- 核心数据（写少读多，用读写锁保护） ---
    private final ReentrantReadWriteLock rwLock = new ReentrantReadWriteLock();
    private final Map<String, Set<String>> rolePermissions = new HashMap<>();
    private final Map<String, Set<String>> userRoles = new HashMap<>();
    // 角色继承：key 的父角色是 value（子角色 -> 父角色列表）
    private final Map<String, Set<String>> roleParents = new HashMap<>();

    // --- 权限缓存 ---
    private final ConcurrentHashMap<String, Boolean> permissionCache = new ConcurrentHashMap<>();

    // ==================== 权限检查 ====================

    public boolean hasPermission(String userId, String permission) {
        String cacheKey = userId + ":" + permission;
        Boolean cached = permissionCache.get(cacheKey);
        if (cached != null) return cached;

        rwLock.readLock().lock();
        try {
            boolean result = doCheckPermission(userId, permission);
            permissionCache.put(cacheKey, result);
            return result;
        } finally {
            rwLock.readLock().unlock();
        }
    }

    private boolean doCheckPermission(String userId, String permission) {
        Set<String> roles = userRoles.getOrDefault(userId, Collections.emptySet());
        for (String role : roles) {
            if (roleHasPermission(role, permission, new HashSet<>())) {
                return true;
            }
        }
        return false;
    }

    /**
     * 递归检查角色及其所有父角色是否拥有指定权限。
     * visited 集合防止循环继承导致无限递归。
     *
     * 继承方向：子角色继承父角色的权限，即父角色有的权限子角色也有，
     * 但子角色自己额外的权限不会向上传递给父角色。
     */
    private boolean roleHasPermission(String role, String permission, Set<String> visited) {
        if (!visited.add(role)) return false; // 检测到循环继承，终止

        // 检查当前角色自身的权限
        Set<String> perms = rolePermissions.getOrDefault(role, Collections.emptySet());
        if (perms.contains(permission)) return true;

        // 向上递归：检查所有父角色的权限
        Set<String> parents = roleParents.getOrDefault(role, Collections.emptySet());
        for (String parent : parents) {
            if (roleHasPermission(parent, permission, visited)) {
                return true;
            }
        }
        return false;
    }

    // ==================== Spring Security PermissionEvaluator 集成 ====================

    @Override
    public boolean hasPermission(Authentication auth, Object targetDomainObject, Object permission) {
        if (auth == null || permission == null) return false;
        String userId = auth.getName();
        return hasPermission(userId, permission.toString());
    }

    @Override
    public boolean hasPermission(Authentication auth, Serializable targetId, String targetType, Object permission) {
        return hasPermission(auth, null, permission);
    }

    // ==================== 数据变更（写操作，清缓存） ====================

    public void assignRole(String userId, String role) {
        rwLock.writeLock().lock();
        try {
            userRoles.computeIfAbsent(userId, k -> new HashSet<>()).add(role);
            invalidateCacheForUser(userId);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public void removeRole(String userId, String role) {
        rwLock.writeLock().lock();
        try {
            Set<String> roles = userRoles.get(userId);
            if (roles != null) {
                roles.remove(role);
            }
            invalidateCacheForUser(userId);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public void grantPermission(String role, String permission) {
        rwLock.writeLock().lock();
        try {
            rolePermissions.computeIfAbsent(role, k -> new HashSet<>()).add(permission);
            invalidateCacheForRole(role);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public void revokePermission(String role, String permission) {
        rwLock.writeLock().lock();
        try {
            Set<String> perms = rolePermissions.get(role);
            if (perms != null) {
                perms.remove(permission);
            }
            invalidateCacheForRole(role);
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    /**
     * 设置角色继承：childRole 继承 parentRole 的权限。
     * 会检测循环继承并拒绝。
     */
    public void setRoleParent(String childRole, String parentRole) {
        rwLock.writeLock().lock();
        try {
            // 先检测加上这条继承关系后是否会产生循环
            if (wouldCreateCycle(childRole, parentRole)) {
                throw new IllegalArgumentException(
                    "添加继承关系 " + childRole + " -> " + parentRole + " 会导致循环继承");
            }
            roleParents.computeIfAbsent(childRole, k -> new HashSet<>()).add(parentRole);
            invalidateAllCache();
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    public void removeRoleParent(String childRole, String parentRole) {
        rwLock.writeLock().lock();
        try {
            Set<String> parents = roleParents.get(childRole);
            if (parents != null) {
                parents.remove(parentRole);
            }
            invalidateAllCache();
        } finally {
            rwLock.writeLock().unlock();
        }
    }

    // ==================== 循环继承检测 ====================

    private boolean wouldCreateCycle(String childRole, String parentRole) {
        // 如果从 parentRole 沿着继承链能走回 childRole，就会产生循环
        Set<String> visited = new HashSet<>();
        Queue<String> queue = new LinkedList<>();
        queue.add(parentRole);
        while (!queue.isEmpty()) {
            String current = queue.poll();
            if (current.equals(childRole)) return true;
            if (!visited.add(current)) continue;
            Set<String> parents = roleParents.getOrDefault(current, Collections.emptySet());
            queue.addAll(parents);
        }
        return false;
    }

    // ==================== 缓存失效 ====================

    private void invalidateCacheForUser(String userId) {
        permissionCache.keySet().removeIf(key -> key.startsWith(userId + ":"));
    }

    private void invalidateCacheForRole(String role) {
        // 角色权限变更影响范围广，需要清除所有持有该角色（含继承）的用户缓存
        invalidateAllCache();
    }

    private void invalidateAllCache() {
        permissionCache.clear();
    }
}
