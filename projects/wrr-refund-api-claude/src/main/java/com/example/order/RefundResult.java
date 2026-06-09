package com.example.order;

public class RefundResult {

    private boolean success;
    private String message;

    public RefundResult(boolean success, String message) {
        this.success = success;
        this.message = message;
    }

    public static RefundResult success(String message) {
        return new RefundResult(true, message);
    }

    public static RefundResult fail(String message) {
        return new RefundResult(false, message);
    }

    public boolean isSuccess() { return success; }
    public String getMessage() { return message; }
}
