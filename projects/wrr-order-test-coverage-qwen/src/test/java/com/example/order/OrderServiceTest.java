package com.example.order;

import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import java.util.Arrays;
import java.util.Collections;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class OrderServiceTest extends PaymentTestBase {

    @Test
    void createOrder_validRequest_returnsOrderWithCreatedStatus() {
        OrderRequest req = new OrderRequest(Arrays.asList("item1", "item2"), "user123");
        Order result = orderService.createOrder(req);
        assertNotNull(result);
        assertEquals("user123", result.getUserId());
        assertEquals("CREATED", result.getStatus());
        assertEquals(0.0, result.getTotal());
    }

    @Test
    void createOrder_nullItems_throwsIllegalArgumentException() {
        OrderRequest req = new OrderRequest(null, "user123");
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class, () -> orderService.createOrder(req));
        assertEquals("Empty order", ex.getMessage());
    }

    @Test
    void createOrder_emptyItems_throwsIllegalArgumentException() {
        OrderRequest req = new OrderRequest(Collections.emptyList(), "user123");
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class, () -> orderService.createOrder(req));
        assertEquals("Empty order", ex.getMessage());
    }

    @Test
    void createOrder_nullUserId_throwsIllegalArgumentException() {
        OrderRequest req = new OrderRequest(Arrays.asList("item1"), null);
        IllegalArgumentException ex = assertThrows(IllegalArgumentException.class, () -> orderService.createOrder(req));
        assertEquals("No user", ex.getMessage());
    }

    @Test
    void cancelOrder_createdOrder_returnsCancelledOrder() {
        Order result = orderService.cancelOrder("order123");
        assertNotNull(result);
        assertEquals("order123", result.getId());
        assertEquals("CANCELLED", result.getStatus());
    }

    @Test
    void cancelOrder_shippedOrder_throwsIllegalStateException() {
        OrderService spyService = Mockito.spy(orderService);
        Order shippedOrder = new Order("order123", "user1", "SHIPPED", 0.0);
        doReturn(shippedOrder).when(spyService).findOrder("order123");

        IllegalStateException ex = assertThrows(IllegalStateException.class, () -> spyService.cancelOrder("order123"));
        assertEquals("Cannot cancel shipped order", ex.getMessage());
    }
}
