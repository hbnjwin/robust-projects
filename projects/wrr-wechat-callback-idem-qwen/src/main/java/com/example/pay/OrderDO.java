package com.example.pay;

import lombok.Data;

@Data
public class OrderDO {
    private Long id;
    private String orderNo;
    private Integer status;
    private Double payAmount;
}
