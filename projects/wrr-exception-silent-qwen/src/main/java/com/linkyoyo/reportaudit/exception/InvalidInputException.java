package com.linkyoyo.reportaudit.exception;

import lombok.Getter;

/**
 * 无效输入异常
 * 当用户提交的输入格式不正确或不符合业务规则时抛出（区别于框架层参数校验）。
 * GlobalExceptionHandler 将此异常映射为 HTTP 400。
 */
@Getter
public class InvalidInputException extends RuntimeException {

    private final String fieldName;

    public InvalidInputException(String fieldName, String detail) {
        super(fieldName + ": " + detail);
        this.fieldName = fieldName;
    }

    public InvalidInputException(String fieldName, String detail, Throwable cause) {
        super(fieldName + ": " + detail, cause);
        this.fieldName = fieldName;
    }
}
