package com.example.order;

import org.springframework.stereotype.Service;
import java.util.*;

@Service
public class OrderService {

    public Order createOrder(OrderRequest req) {
        if (req.getItems() == null || req.getItems().isEmpty()) throw new IllegalArgumentException("Empty order");
        if (req.getUserId() == null) throw new IllegalArgumentException("No user");
        return new Order(UUID.randomUUID().toString(), req.getUserId(), "CREATED", calculateTotal(req));
    }

    public Order cancelOrder(String orderId) {
        Order order = findOrder(orderId);
        if ("SHIPPED".equals(order.getStatus())) throw new IllegalStateException("Cannot cancel shipped order");
        order.setStatus("CANCELLED");
        return order;
    }

    private double calculateTotal(OrderRequest req) { return 0.0; }
    Order findOrder(String id) { return new Order(id, "user1", "CREATED", 0.0); }
}
