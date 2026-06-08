package com.example.order;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OrderServiceTest extends PaymentTestBase {

    private OrderService orderService;

    @BeforeEach
    void setUp() {
        orderService = new OrderService();
    }

    // ==================== createOrder tests ====================

    @Test
    void createOrder_nullItems_throwsIllegalArgumentException() {
        OrderRequest req = new OrderRequest("user1", null);
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                () -> orderService.createOrder(req));
        assertEquals("Empty order", ex.getMessage());
    }

    @Test
    void createOrder_emptyItems_throwsIllegalArgumentException() {
        OrderRequest req = new OrderRequest("user1", Collections.emptyList());
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                () -> orderService.createOrder(req));
        assertEquals("Empty order", ex.getMessage());
    }

    @Test
    void createOrder_nullUserId_throwsIllegalArgumentException() {
        OrderRequest req = new OrderRequest(null, Arrays.asList("item1"));
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class,
                () -> orderService.createOrder(req));
        assertEquals("No user", ex.getMessage());
    }

    @Test
    void createOrder_validRequest_returnsCreatedOrder() {
        OrderRequest req = new OrderRequest("user1", Arrays.asList("item1", "item2"));
        Order order = orderService.createOrder(req);

        assertNotNull(order);
        assertNotNull(order.getId());
        assertEquals("user1", order.getUserId());
        assertEquals("CREATED", order.getStatus());
        assertEquals(0.0, order.getTotal());
    }

    @Test
    void createOrder_singleItem_returnsCreatedOrder() {
        OrderRequest req = new OrderRequest("user42", Arrays.asList("itemA"));
        Order order = orderService.createOrder(req);

        assertNotNull(order.getId());
        assertEquals("user42", order.getUserId());
        assertEquals("CREATED", order.getStatus());
    }

    // ==================== cancelOrder tests ====================

    @Test
    void cancelOrder_nonShippedOrder_returnsCancelledOrder() {
        Order order = orderService.cancelOrder("order-123");

        assertNotNull(order);
        assertEquals("order-123", order.getId());
        assertEquals("CANCELLED", order.getStatus());
    }

    @Test
    void cancelOrder_shippedOrder_throwsIllegalStateException() {
        OrderService spyService = Mockito.spy(orderService);
        Order shippedOrder = new Order("order-456", "user1", "SHIPPED", 100.0);
        doReturn(shippedOrder).when(spyService).findOrder("order-456");

        IllegalStateException ex = assertThrows(IllegalStateException.class,
                () -> spyService.cancelOrder("order-456"));
        assertEquals("Cannot cancel shipped order", ex.getMessage());
    }

    @Test
    void cancelOrder_createdOrder_statusSetToCancelled() {
        OrderService spyService = Mockito.spy(orderService);
        Order createdOrder = new Order("order-789", "user2", "CREATED", 50.0);
        doReturn(createdOrder).when(spyService).findOrder("order-789");

        Order result = spyService.cancelOrder("order-789");

        assertEquals("CANCELLED", result.getStatus());
        assertEquals("user2", result.getUserId());
        assertEquals(50.0, result.getTotal());
    }

    @Test
    void cancelOrder_pendingOrder_returnsCancelledOrder() {
        OrderService spyService = Mockito.spy(orderService);
        Order pendingOrder = new Order("order-abc", "user3", "PENDING", 25.0);
        doReturn(pendingOrder).when(spyService).findOrder("order-abc");

        Order result = spyService.cancelOrder("order-abc");

        assertEquals("CANCELLED", result.getStatus());
    }
}
