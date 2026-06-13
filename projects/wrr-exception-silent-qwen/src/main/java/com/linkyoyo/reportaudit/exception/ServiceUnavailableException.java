package com.linkyoyo.reportaudit.exception;

import lombok.Getter;

/**
 * 外部服务不可用异常
 * 当依赖的外部服务（如 OCR 服务、第三方 API）无法访问或超时时抛出。
 * GlobalExceptionHandler 将此异常映射为 HTTP 503。
 */
@Getter
public class ServiceUnavailableException extends RuntimeException {

    private final String serviceName;

    public ServiceUnavailableException(String serviceName, String detail) {
        super(serviceName + "服务不可用: " + detail);
        this.serviceName = serviceName;
    }

    public ServiceUnavailableException(String serviceName, String detail, Throwable cause) {
        super(serviceName + "服务不可用: " + detail, cause);
        this.serviceName = serviceName;
    }
}
