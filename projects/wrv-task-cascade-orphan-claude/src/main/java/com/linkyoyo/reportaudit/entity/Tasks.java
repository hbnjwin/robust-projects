package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;
import java.time.LocalDateTime;

@Data
@Entity
@Table(name = "tasks")
public class Tasks {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private Long documentId;
    private String status; // queued, started, completed, failed
    private Integer priority;
    private Integer retryCount;
    private LocalDateTime createdAt;
    private LocalDateTime completedAt;
}
