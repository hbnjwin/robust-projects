package com.example.correction;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("ai_correction")
public class CorrectionDO {
    @TableId
    private Long id;
    private Long classId;
    private Long homeworkId;
    private Long teacherId;
    private String status;
    private LocalDateTime createTime;
}
