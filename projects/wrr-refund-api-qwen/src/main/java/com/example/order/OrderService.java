package com.example.order;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class OrderService {

    private static final Logger log = LoggerFactory.getLogger(OrderService.class);

    private final OrderRepository orderRepository;
    private final PaymentClient paymentClient;

    public OrderService(OrderRepository orderRepository, PaymentClient paymentClient) {
        this.orderRepository = orderRepository;
        this.paymentClient = paymentClient;
    }

    /**
     * Refund an order.
     * Rules:
     *   1. Order must exist
     *   2. Order status must be PAID (paid and not yet shipped)
     *   3. Payment center refund must succeed
     * On success the order status is updated to REFUNDED.
     */
    public RefundResponse refund(String orderId) {
        // 1. Find order
        Order order = orderRepository.findById(orderId);
        if (order == null) {
            throw new RefundException("Order not found", orderId);
        }

        // 2. Validate status: only PAID orders (paid but not shipped) can be refunded
        if (order.getStatus() != OrderStatus.PAID) {
            throw new RefundException(
                    "Order cannot be refunded: current status is " + order.getStatus()
                            + ", only PAID (not yet shipped) orders are eligible",
                    orderId
            );
        }

        // 3. Call payment center refund API
        boolean refundOk = paymentClient.refund(order.getOrderId(), order.getAmount());
        if (!refundOk) {
            throw new RefundException("Payment center refund failed, please retry later", orderId);
        }

        // 4. Update order status
        order.setStatus(OrderStatus.REFUNDED);
        orderRepository.save(order);
        log.info("Order refunded successfully: orderId={}, amount={}", orderId, order.getAmount());

        return new RefundResponse(true, "Refund successful", orderId);
    }
}
