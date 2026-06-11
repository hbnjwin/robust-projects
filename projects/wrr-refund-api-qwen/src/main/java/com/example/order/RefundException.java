package com.example.order;

public class RefundException extends RuntimeException {
    private final String orderId;

    public RefundException(String message, String orderId) {
        super(message);
        this.orderId = orderId;
    }

    public String getOrderId() { return orderId; }
}
