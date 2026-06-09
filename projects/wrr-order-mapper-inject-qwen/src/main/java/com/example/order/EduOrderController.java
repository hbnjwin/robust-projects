package com.example.order;

import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/edu/order")
public class EduOrderController {

    // BUG: Controller 直接注入了 Mapper，跳过 Service 层
    // 导致：1) 事务管理没有生效  2) 数据权限拦截器被绕过
    // 应该通过 EduOrderService 来操作数据
    @Resource
    private EduOrderMapper orderMapper;

    @Resource
    private PaymentRecordMapper paymentMapper;

    @GetMapping("/list")
    public Map<String, Object> listOrders(@RequestParam Long userId,
                                          @RequestParam(required = false) Integer status) {
        // BUG: 直接用 Mapper 查询，绕过了 Service 层的数据权限控制
        LambdaQueryWrapper<EduOrderDO> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(EduOrderDO::getUserId, userId);
        if (status != null) {
            wrapper.eq(EduOrderDO::getStatus, status);
        }
        wrapper.orderByDesc(EduOrderDO::getCreateTime);
        List<EduOrderDO> orders = orderMapper.selectList(wrapper);

        return Map.of("code", 0, "data", orders);
    }

    @GetMapping("/detail")
    public Map<String, Object> getOrderDetail(@RequestParam Long orderId) {
        // BUG: 直接用 Mapper 查询，没有数据权限校验
        // 任何用户可以查看任何人的订单
        EduOrderDO order = orderMapper.selectById(orderId);
        // BUG: 也直接用了 PaymentRecordMapper
        var payments = paymentMapper.selectList(
            new LambdaQueryWrapper<PaymentRecordDO>()
                .eq(PaymentRecordDO::getOrderId, orderId)
        );

        return Map.of("code", 0, "data", Map.of("order", order, "payments", payments));
    }

    @PostMapping("/cancel")
    public Map<String, Object> cancelOrder(@RequestParam Long orderId) {
        // BUG: 没有事务控制
        // 如果取消订单时需要同时更新订单状态和退款记录，操作不是原子的
        EduOrderDO order = orderMapper.selectById(orderId);
        order.setStatus(2); // 已取消
        orderMapper.updateById(order);

        // 如果这里失败了，订单已经标记取消但退款记录没写入
        PaymentRecordDO refund = new PaymentRecordDO();
        refund.setOrderId(orderId);
        refund.setType("refund");
        refund.setAmount(order.getPayPrice());
        paymentMapper.insert(refund);

        return Map.of("code", 0, "msg", "取消成功");
    }
}
