package com.example.order;

import java.util.List;

public class OrderRequest {
    private List<String> items;
    private String userId;

    public OrderRequest(List<String> items, String userId) {
        this.items = items;
        this.userId = userId;
    }

    public List<String> getItems() { return items; }
    public String getUserId() { return userId; }
}
