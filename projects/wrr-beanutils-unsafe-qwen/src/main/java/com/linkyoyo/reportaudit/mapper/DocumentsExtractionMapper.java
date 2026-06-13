package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.DocumentsExtraction;
import com.linkyoyo.reportaudit.info.DocumentsExtractionInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface DocumentsExtractionMapper {

    DocumentsExtractionInfo toInfo(DocumentsExtraction entity);
}
