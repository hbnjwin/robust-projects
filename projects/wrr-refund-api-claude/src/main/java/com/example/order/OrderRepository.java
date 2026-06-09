package com.example.order;

import org.springframework.stereotype.Repository;

import javax.annotation.PostConstruct;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Repository
public class OrderRepository {

    private final Map<String, Order> store = new ConcurrentHashMap<>();

    @PostConstruct
    public void init() {
        store.put("ORD001", new Order("ORD001", "PAID", 100.00));
        store.put("ORD002", new Order("ORD002", "SHIPPED", 200.00));
        store.put("ORD003", new Order("ORD003", "UNPAID", 50.00));
    }

    public Optional<Order> findById(String orderId) {
        return Optional.ofNullable(store.get(orderId));
    }

    public void save(Order order) {
        store.put(order.getOrderId(), order);
    }
}
