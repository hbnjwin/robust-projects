package com.example.homework;

import lombok.Data;

@Data
public class ManualGradeReq {
    private Long homeworkId;
    private Long studentId;
    private Integer score;
    private String comment;
}
