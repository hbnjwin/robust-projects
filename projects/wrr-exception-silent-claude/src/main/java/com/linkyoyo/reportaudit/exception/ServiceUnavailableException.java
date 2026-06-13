package com.linkyoyo.reportaudit.exception;

import lombok.Getter;

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
