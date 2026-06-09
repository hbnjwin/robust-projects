package com.example.order;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("payment_record")
public class PaymentRecordDO {
    @TableId
    private Long id;
    private Long orderId;
    private String type;
    private Double amount;
}
