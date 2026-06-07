package com.example.security;

import org.springframework.security.core.*;
import org.springframework.security.access.annotation.*;
import java.util.*;

@Service
public class RbacService {

    private Map<String, Set<String>> rolePermissions = new HashMap<>();
    private Map<String, Set<String>> userRoles = new HashMap<>();

    public boolean hasPermission(String userId, String permission) {
        Set<String> roles = userRoles.getOrDefault(userId, Collections.emptySet());
        for (String role : roles) {
            Set<String> perms = rolePermissions.getOrDefault(role, Collections.emptySet());
            if (perms.contains(permission)) return true;
            // Check parent roles recursively
            if (checkParentRoles(role, permission)) return true;
        }
        return false;
    }

    private boolean checkParentRoles(String role, String permission) {
        // Complex inheritance logic - needs explanation
        return false;
    }
}
