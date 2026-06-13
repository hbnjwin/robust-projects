package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.entity.DocumentsCheckItems;
import com.linkyoyo.reportaudit.entity.DocumentsExtraction;
import com.linkyoyo.reportaudit.entity.DocumentsToc;
import com.linkyoyo.reportaudit.entity.ProjectInfo;
import com.linkyoyo.reportaudit.info.DocumentsCheckItemsInfo;
import com.linkyoyo.reportaudit.info.DocumentsExtractionInfo;
import com.linkyoyo.reportaudit.info.DocumentsInfo;
import com.linkyoyo.reportaudit.info.DocumentsTocInfo;
import com.linkyoyo.reportaudit.info.ProjectInfoInfo;
import org.mapstruct.Mapper;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

import java.util.List;

// TODO: unmappedTargetPolicy 升级为 ERROR，待所有字段映射确认完毕后启用
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.WARN)
public interface DocumentsMapper {

    // --- Documents <-> DocumentsInfo ---

    DocumentsInfo toInfo(Documents entity);

    Documents toEntity(DocumentsInfo info);

    void updateEntity(DocumentsInfo info, @MappingTarget Documents entity);

    // --- DocumentsToc <-> DocumentsTocInfo ---

    DocumentsTocInfo tocToInfo(DocumentsToc entity);

    DocumentsToc tocToEntity(DocumentsTocInfo info);

    List<DocumentsTocInfo> tocListToInfoList(List<DocumentsToc> entities);

    // --- ProjectInfo -> ProjectInfoInfo ---

    ProjectInfoInfo projectInfoToInfo(ProjectInfo entity);

    // --- DocumentsExtraction -> DocumentsExtractionInfo ---

    DocumentsExtractionInfo extractionToInfo(DocumentsExtraction entity);

    List<DocumentsExtractionInfo> extractionListToInfoList(List<DocumentsExtraction> entities);

    // --- DocumentsCheckItems -> DocumentsCheckItemsInfo ---

    DocumentsCheckItemsInfo checkItemsToInfo(DocumentsCheckItems entity);

    List<DocumentsCheckItemsInfo> checkItemsListToInfoList(List<DocumentsCheckItems> entities);
}
