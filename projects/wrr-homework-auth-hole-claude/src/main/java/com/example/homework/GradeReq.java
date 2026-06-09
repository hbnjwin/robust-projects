package com.example.homework;

import lombok.Data;

@Data
public class GradeReq {
    private Long homeworkId;
    private Long studentId;
    private Integer score;
    private String comment;
}
