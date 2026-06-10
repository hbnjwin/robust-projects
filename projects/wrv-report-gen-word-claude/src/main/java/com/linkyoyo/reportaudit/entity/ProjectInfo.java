package com.linkyoyo.reportaudit.entity;

import lombok.Data;
import javax.persistence.*;

@Data
@Entity
@Table(name = "project_info")
public class ProjectInfo {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String projectName;
    private String province;
    private String city;
    private String reportType;
    private Integer windTowerCount;
    private Integer turbineCount;
    private String longitude;
    private String latitude;
}
