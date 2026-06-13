package com.linkyoyo.reportaudit.exception;

import lombok.Getter;

@Getter
public class EntityNotFoundException extends RuntimeException {

    private final String entityType;
    private final String entityId;

    public EntityNotFoundException(String entityType, String entityId) {
        super("未找到" + entityType + ", ID: " + entityId);
        this.entityType = entityType;
        this.entityId = entityId;
    }
}
