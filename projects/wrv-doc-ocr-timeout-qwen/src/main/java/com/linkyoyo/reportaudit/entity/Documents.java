package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "documents")
public class Documents {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private String filePath;
    private String ocrStatus; // UPLOADED, OCR_PROCESSING, OCR_COMPLETED, OCR_FAILED
    private String contentType;
    private Long fileSize;
    private LocalDateTime createdAt;
}
