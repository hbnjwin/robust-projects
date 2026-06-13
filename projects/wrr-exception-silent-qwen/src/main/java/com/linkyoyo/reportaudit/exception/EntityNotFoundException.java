package com.linkyoyo.reportaudit.exception;

import lombok.Getter;

/**
 * 实体未找到异常
 * 当通过 ID 或其他唯一标识查询数据库实体但结果为空时抛出。
 * GlobalExceptionHandler 将此异常映射为 HTTP 404。
 */
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
