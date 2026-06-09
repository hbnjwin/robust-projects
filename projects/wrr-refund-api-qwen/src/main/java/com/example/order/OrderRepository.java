package com.example.order;

import org.springframework.stereotype.Repository;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Repository
public class OrderRepository {

    private final Map<String, Order> store = new ConcurrentHashMap<>();

    public OrderRepository() {
        // seed some test data
        store.put("ORD-001", new Order("ORD-001", OrderStatus.PAID, 199.00));
        store.put("ORD-002", new Order("ORD-002", OrderStatus.SHIPPED, 299.00));
        store.put("ORD-003", new Order("ORD-003", OrderStatus.PENDING, 99.00));
    }

    public Order findById(String orderId) {
        return store.get(orderId);
    }

    public void save(Order order) {
        store.put(order.getOrderId(), order);
    }
}
