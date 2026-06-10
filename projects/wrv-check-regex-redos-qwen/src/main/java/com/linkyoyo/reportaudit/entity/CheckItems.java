package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;

@Data
@Entity
@Table(name = "check_items")
public class CheckItems {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String name;
    private String keyword;
    private String regex;
    private String prompt;
    private String description;
}
