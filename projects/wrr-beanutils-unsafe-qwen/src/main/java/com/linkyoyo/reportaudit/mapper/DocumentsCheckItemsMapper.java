package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.DocumentsCheckItems;
import com.linkyoyo.reportaudit.info.DocumentsCheckItemsInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface DocumentsCheckItemsMapper {

    DocumentsCheckItemsInfo toInfo(DocumentsCheckItems entity);
}
