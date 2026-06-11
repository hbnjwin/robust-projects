package com.example.pay;

import org.springframework.stereotype.Service;
import jakarta.annotation.Resource;

@Service
public class WeChatPayService {

    @Resource
    private OrderMapper orderMapper;

    public boolean verifySignature(String body, String signature) {
        // 简化：实际需要用微信平台证书验签
        return body != null && !body.isEmpty() && signature != null;
    }

    public PayNotification parseNotification(String body) {
        // 简化：实际需要 AES 解密
        PayNotification n = new PayNotification();
        n.setOrderNo("ORDER_001");
        n.setAmount(9990); // 单位：分
        return n;
    }

    public void handlePaySuccess(String orderNo, int amountFen) {
        // BUG: 没有幂等性检查
        // 不检查订单当前状态就直接更新
        // 如果订单已经是 "已支付" 状态，会重复执行支付后逻辑
        var order = orderMapper.selectByOrderNo(orderNo);
        // BUG: 没有检查 order.getStatus() == 0 (待支付)
        order.setStatus(1); // 直接设为已支付
        order.setPayAmount(amountFen / 100.0); // BUG: 重复累加？实际场景可能更复杂
        orderMapper.updateById(order);

        // 触发后续业务（开通课程、发消息等）
        // BUG: 这些操作也没有幂等保护，会重复执行
    }
}
