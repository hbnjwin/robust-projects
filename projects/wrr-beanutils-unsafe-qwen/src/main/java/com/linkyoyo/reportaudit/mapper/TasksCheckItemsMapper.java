package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.TasksCheckItems;
import com.linkyoyo.reportaudit.info.TasksCheckItemsInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface TasksCheckItemsMapper {

    TasksCheckItemsInfo toInfo(TasksCheckItems entity);

    TasksCheckItems toEntity(TasksCheckItemsInfo info);
}
