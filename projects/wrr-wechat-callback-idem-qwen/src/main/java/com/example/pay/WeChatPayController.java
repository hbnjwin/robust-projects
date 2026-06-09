package com.example.pay;

import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletRequest;
import java.io.BufferedReader;
import java.io.IOException;
import java.util.Map;

@RestController
@RequestMapping("/api/pay/wechat")
public class WeChatPayController {

    @Resource
    private WeChatPayService payService;

    @PostMapping("/notify")
    public Map<String, String> handlePayNotify(HttpServletRequest request) throws IOException {
        // BUG: HttpServletRequest 的 body（InputStream）只能读取一次
        // 第一次读取：框架层面可能已经读过（如 Spring 的 RequestBody 解析）
        // 第二次读取：这里再读就是空的，导致验签失败
        String body = readRequestBody(request);

        // 验签
        String signature = request.getHeader("Wechatpay-Signature");
        if (!payService.verifySignature(body, signature)) {
            // BUG: body 可能是空的（因为被读过了），验签必然失败
            return Map.of("code", "FAIL", "message", "验签失败");
        }

        // 解析通知内容
        PayNotification notification = payService.parseNotification(body);

        // BUG: 没有幂等性检查
        // 微信可能重复发送回调通知（网络超时重试）
        // 同一笔支付通知处理两次会导致订单金额翻倍或状态异常
        payService.handlePaySuccess(notification.getOrderNo(), notification.getAmount());

        return Map.of("code", "SUCCESS", "message", "OK");
    }

    private String readRequestBody(HttpServletRequest request) throws IOException {
        // BUG: 如果 body 已经被读取过，这里读到的是空字符串
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = request.getReader()) {
            String line;
            while ((line = reader.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }
}
