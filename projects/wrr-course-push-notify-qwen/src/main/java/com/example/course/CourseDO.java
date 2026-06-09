package com.example.course;

import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("edu_course")
public class CourseDO {
    @TableId
    private Long id;
    private String name;
    private String description;
    private Long teacherId;
    private Boolean distributed;
}
