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
    private Double payPrice;
    private Integer status;
    private LocalDateTime createTime;
}
