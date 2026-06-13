package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.DocumentsToc;
import com.linkyoyo.reportaudit.info.DocumentsTocInfo;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface DocumentsTocMapper {

    DocumentsTocInfo toInfo(DocumentsToc entity);

    DocumentsToc toEntity(DocumentsTocInfo info);
}
