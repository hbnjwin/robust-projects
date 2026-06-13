package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.info.DocumentsInfo;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;

@Mapper(componentModel = "spring")
public interface DocumentsMapper {

    DocumentsInfo toInfo(Documents entity);

    Documents toEntity(DocumentsInfo info);

    void updateEntity(DocumentsInfo info, @MappingTarget Documents entity);
}
