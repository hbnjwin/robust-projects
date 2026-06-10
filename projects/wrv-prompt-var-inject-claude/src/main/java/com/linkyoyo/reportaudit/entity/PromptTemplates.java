package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;

@Data
@Entity
@Table(name = "prompt_templates")
public class PromptTemplates {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    @Column(columnDefinition = "TEXT")
    private String content;
    private Double score;
    private String modelName;
}
