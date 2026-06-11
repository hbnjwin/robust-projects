package com.example.order;

import org.springframework.stereotype.Service;

@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final PaymentCenterClient paymentCenterClient;

    public OrderService(OrderRepository orderRepository, PaymentCenterClient paymentCenterClient) {
        this.orderRepository = orderRepository;
        this.paymentCenterClient = paymentCenterClient;
    }

    public RefundResult refund(String orderId) {
        Order order = orderRepository.findById(orderId)
                .orElse(null);

        if (order == null) {
            return RefundResult.fail("订单不存在");
        }

        if (!"PAID".equals(order.getStatus())) {
            return RefundResult.fail("订单状态不是已支付，无法退款");
        }

        boolean refundSuccess = paymentCenterClient.refund(orderId, order.getAmount());
        if (!refundSuccess) {
            return RefundResult.fail("调用支付中心退款失败");
        }

        order.setStatus("REFUNDED");
        orderRepository.save(order);

        return RefundResult.success("退款成功");
    }
}
