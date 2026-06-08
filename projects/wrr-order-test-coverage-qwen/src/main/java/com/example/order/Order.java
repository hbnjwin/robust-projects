package com.example.order;

import java.util.List;

public class Order {
    private String id;
    private String userId;
    private String status;
    private double total;

    public Order(String id, String userId, String status, double total) {
        this.id = id;
        this.userId = userId;
        this.status = status;
        this.total = total;
    }

    public String getId() { return id; }
    public String getUserId() { return userId; }
    public String getStatus() { return status; }
    public double getTotal() { return total; }
    public void setStatus(String status) { this.status = status; }
}
