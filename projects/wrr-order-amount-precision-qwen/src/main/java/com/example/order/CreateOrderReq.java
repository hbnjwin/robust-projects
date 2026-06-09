package com.example.order;

import lombok.Data;

@Data
public class CreateOrderReq {
    private Long userId;
    private Long courseId;
    private String courseName;
    private Double originalPrice;
    private Double discountRate;
}
