package com.example.order;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

/**
 * Client for calling the external payment center refund API.
 */
@Component
public class PaymentClient {

    private static final Logger log = LoggerFactory.getLogger(PaymentClient.class);

    private final RestTemplate restTemplate;

    @Value("${payment.center.url:http://localhost:8081}")
    private String paymentCenterUrl;

    public PaymentClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * Call payment center to refund the given order.
     *
     * @return true if the payment center accepted the refund
     */
    public boolean refund(String orderId, double amount) {
        String url = paymentCenterUrl + "/api/payments/refund";
        Map<String, Object> request = Map.of(
                "orderId", orderId,
                "amount", amount
        );

        try {
            log.info("Calling payment center refund: orderId={}, amount={}", orderId, amount);
            restTemplate.postForEntity(url, request, Map.class);
            log.info("Payment center refund succeeded: orderId={}", orderId);
            return true;
        } catch (Exception e) {
            log.error("Payment center refund failed: orderId={}, error={}", orderId, e.getMessage());
            return false;
        }
    }
}
