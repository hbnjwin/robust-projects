package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.info.ExtractionTasksInfo;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;

@Mapper(componentModel = "spring")
public interface ExtractionTasksMapper {

    ExtractionTasks toEntity(ExtractionTasksInfo info);

    void updateEntity(ExtractionTasksInfo info, @MappingTarget ExtractionTasks entity);
}
