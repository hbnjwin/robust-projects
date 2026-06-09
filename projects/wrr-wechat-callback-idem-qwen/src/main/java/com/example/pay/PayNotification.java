package com.example.pay;

import lombok.Data;

@Data
public class PayNotification {
    private String orderNo;
    private int amount; // 单位：分
}
