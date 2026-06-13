package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.ExtractionResult;
import com.linkyoyo.reportaudit.info.ExtractionResultInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface ExtractionResultMapper {

    ExtractionResult toEntity(ExtractionResultInfo info);
}
