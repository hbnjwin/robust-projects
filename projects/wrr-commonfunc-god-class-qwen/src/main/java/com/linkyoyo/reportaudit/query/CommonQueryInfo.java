package com.linkyoyo.reportaudit.query;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class CommonQueryInfo {
    private String  tableName ;
    private String  fields;
    private String  where;
    private String  keyWord ;
    private String  sort;
    private String  sql;
}
