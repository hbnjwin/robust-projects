package com.example.correction;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("ai_paper_correction_task")
public class PaperCorrectionTaskDO {
    @TableId
    private Long id;
    private Long correctionId;
    private Long studentId;
    private String status;
    private String aiComment;
    private Integer aiScore;
}
