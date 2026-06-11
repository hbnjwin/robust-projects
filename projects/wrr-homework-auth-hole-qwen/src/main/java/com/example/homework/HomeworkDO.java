package com.example.homework;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("edu_homework")
public class HomeworkDO {
    @TableId
    private Long id;
    private Long classId;
    private Long teacherId;
    private String title;
    private String content;
    private String requirements;
    private LocalDateTime deadline;
    private Integer status;
    private LocalDateTime createTime;
}
