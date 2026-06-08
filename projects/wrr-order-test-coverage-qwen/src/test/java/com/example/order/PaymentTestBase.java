package com.example.order;

import org.junit.jupiter.api.BeforeEach;

public abstract class PaymentTestBase {
    protected OrderService orderService;

    @BeforeEach
    void setUp() {
        orderService = new OrderService();
    }
}
