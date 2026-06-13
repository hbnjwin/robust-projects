package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.CheckResult;
import com.linkyoyo.reportaudit.info.CheckResultInfo;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;

@Mapper(componentModel = "spring")
public interface CheckResultMapper {

    CheckResultInfo toInfo(CheckResult entity);

    CheckResult toEntity(CheckResultInfo info);

    void updateEntity(CheckResultInfo info, @MappingTarget CheckResult entity);
}
