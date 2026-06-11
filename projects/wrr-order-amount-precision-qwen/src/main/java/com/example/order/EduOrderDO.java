package com.example.order;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("edu_order")
public class EduOrderDO {

    @TableId
    private Long id;
    private Long userId;
    private Long courseId;
    private String courseName;

    // BUG: 使用 Double 存储金额，会导致浮点精度丢失
    // 99.9 会变成 99.89999999999999
    // 应该使用 BigDecimal
    private Double originalPrice;
    private Double discountPrice;
    private Double payPrice;

    private Integer status; // 0-待支付 1-已支付 2-已取消
    private String payChannel; // wechat/alipay
    private LocalDateTime payTime;
    private LocalDateTime createTime;
}
