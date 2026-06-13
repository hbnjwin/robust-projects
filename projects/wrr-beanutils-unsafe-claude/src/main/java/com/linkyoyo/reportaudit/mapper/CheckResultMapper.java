package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.CheckResult;
import com.linkyoyo.reportaudit.info.CheckResultInfo;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

// TODO: unmappedTargetPolicy 升级为 ERROR，待所有字段映射确认完毕后启用
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.WARN)
public interface CheckResultMapper {

    CheckResultInfo toInfo(CheckResult entity);

    CheckResult toEntity(CheckResultInfo info);

    void updateEntity(CheckResultInfo info, @MappingTarget CheckResult entity);
}
