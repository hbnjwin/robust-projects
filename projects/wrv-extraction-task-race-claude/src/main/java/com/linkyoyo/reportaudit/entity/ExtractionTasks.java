package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "extraction_tasks")
public class ExtractionTasks {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String status; // queued, running, completed, failed
    private Long configId;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
