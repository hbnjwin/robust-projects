package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.ProjectInfo;
import com.linkyoyo.reportaudit.info.ProjectInfoInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface ProjectInfoMapper {

    ProjectInfoInfo toInfo(ProjectInfo entity);
}
