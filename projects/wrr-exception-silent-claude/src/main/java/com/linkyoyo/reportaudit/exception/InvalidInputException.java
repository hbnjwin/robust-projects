package com.linkyoyo.reportaudit.exception;

import lombok.Getter;

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
