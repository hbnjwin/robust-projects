package com.example.order;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Component
public class PaymentCenterClient {

    private static final Logger log = LoggerFactory.getLogger(PaymentCenterClient.class);

    private final RestTemplate restTemplate;

    @Value("${payment.center.url:http://payment-center:8080}")
    private String paymentCenterUrl;

    public PaymentCenterClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    public boolean refund(String orderId, double amount) {
        String url = paymentCenterUrl + "/api/refund";
        Map<String, Object> request = new HashMap<>();
        request.put("orderId", orderId);
        request.put("amount", amount);

        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(url, request, Map.class);
            return response.getStatusCode().is2xxSuccessful();
        } catch (RestClientException e) {
            log.error("Failed to call payment center refund API for order {}: {}", orderId, e.getMessage());
            return false;
        }
    }
}
