package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.ExtractionTasksItems;
import com.linkyoyo.reportaudit.info.ExtractionTasksItemsInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface ExtractionTasksItemsMapper {

    ExtractionTasksItems toEntity(ExtractionTasksItemsInfo info);
}
