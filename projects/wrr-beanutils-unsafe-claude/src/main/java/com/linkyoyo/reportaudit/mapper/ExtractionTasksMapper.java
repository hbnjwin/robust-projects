package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.ExtractionResult;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.ExtractionTasksItems;
import com.linkyoyo.reportaudit.info.ExtractionResultInfo;
import com.linkyoyo.reportaudit.info.ExtractionTasksInfo;
import com.linkyoyo.reportaudit.info.ExtractionTasksItemsInfo;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

// TODO: unmappedTargetPolicy 升级为 ERROR，待所有字段映射确认完毕后启用
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.WARN)
public interface ExtractionTasksMapper {

    // --- ExtractionTasks ---

    ExtractionTasks toEntity(ExtractionTasksInfo info);

    void updateEntity(ExtractionTasksInfo info, @MappingTarget ExtractionTasks entity);

    // --- ExtractionResult ---

    ExtractionResult resultToEntity(ExtractionResultInfo info);

    // --- ExtractionTasksItems ---

    ExtractionTasksItems itemsToEntity(ExtractionTasksItemsInfo info);
}
