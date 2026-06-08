package com.example.order;

import java.util.List;

public class OrderRequest {
    private String userId;
    private List<String> items;

    public OrderRequest() {}

    public OrderRequest(String userId, List<String> items) {
        this.userId = userId;
        this.items = items;
    }

    public String getUserId() { return userId; }
    public void setUserId(String userId) { this.userId = userId; }
    public List<String> getItems() { return items; }
    public void setItems(List<String> items) { this.items = items; }
}
