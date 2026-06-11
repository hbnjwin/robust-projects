package com.example.order;

public class RefundResponse {
    private boolean success;
    private String message;
    private String orderId;

    public RefundResponse(boolean success, String message, String orderId) {
        this.success = success;
        this.message = message;
        this.orderId = orderId;
    }

    public boolean isSuccess() { return success; }
    public String getMessage() { return message; }
    public String getOrderId() { return orderId; }
}
