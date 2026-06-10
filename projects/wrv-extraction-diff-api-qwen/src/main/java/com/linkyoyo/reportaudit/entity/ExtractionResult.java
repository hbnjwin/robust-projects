package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;

@Data
@Entity
@Table(name = "extraction_result")
public class ExtractionResult {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private Long executionId;
    private String fieldName;
    private String fieldValue;
    private Double confidence;
}
