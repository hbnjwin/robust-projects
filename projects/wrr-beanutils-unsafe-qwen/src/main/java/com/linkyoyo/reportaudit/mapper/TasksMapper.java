package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.info.TasksInfo;
import org.mapstruct.BeanMapping;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.MappingTarget;

@Mapper(componentModel = "spring")
public interface TasksMapper {

    TasksInfo toInfo(Tasks entity);

    Tasks toEntity(TasksInfo info);

    @BeanMapping(ignoreByDefault = false)
    @Mapping(target = "title", ignore = true)
    @Mapping(target = "status", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    @Mapping(target = "startedAt", ignore = true)
    @Mapping(target = "completedAt", ignore = true)
    @Mapping(target = "result", ignore = true)
    @Mapping(target = "error", ignore = true)
    @Mapping(target = "creater", ignore = true)
    @Mapping(target = "deptId", ignore = true)
    @Mapping(target = "operatorCode", ignore = true)
    @Mapping(target = "progress", ignore = true)
    void updateEntity(TasksInfo info, @MappingTarget Tasks entity);
}
