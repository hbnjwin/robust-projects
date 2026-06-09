package com.example.order;

import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import java.util.Map;

@RestController
@RequestMapping("/api/edu/order")
public class EduOrderController {

    @Resource
    private EduOrderService orderService;

    @PostMapping("/create")
    public Map<String, Object> createOrder(@RequestBody CreateOrderReq req) {
        EduOrderDO order = new EduOrderDO();
        order.setUserId(req.getUserId());
        order.setCourseId(req.getCourseId());
        order.setCourseName(req.getCourseName());
        order.setOriginalPrice(req.getOriginalPrice());

        // BUG: Double 运算导致精度丢失
        // 例如 99.9 * 0.8 = 79.92000000000002 而不是 79.92
        double discount = req.getDiscountRate() != null ? req.getDiscountRate() : 1.0;
        order.setDiscountPrice(order.getOriginalPrice() * (1 - discount));
        order.setPayPrice(order.getOriginalPrice() * discount);

        order.setStatus(0);
        orderService.save(order);

        return Map.of("code", 0, "data", Map.of("orderId", order.getId(), "payPrice", order.getPayPrice()));
    }

    @GetMapping("/summary")
    public Map<String, Object> getOrderSummary(@RequestParam Long userId) {
        var orders = orderService.listByUserId(userId);
        // BUG: Double 累加导致误差积累
        double totalPaid = 0.0;
        for (EduOrderDO o : orders) {
            if (o.getStatus() == 1) {
                totalPaid += o.getPayPrice();  // BUG: Double 累加
            }
        }
        return Map.of("code", 0, "data", Map.of("totalPaid", totalPaid));
    }
}
