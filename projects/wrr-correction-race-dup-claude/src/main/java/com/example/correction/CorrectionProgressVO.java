package com.example.correction;

import lombok.Data;

@Data
public class CorrectionProgressVO {
    private int total;
    private int corrected;
    private String status;
}
