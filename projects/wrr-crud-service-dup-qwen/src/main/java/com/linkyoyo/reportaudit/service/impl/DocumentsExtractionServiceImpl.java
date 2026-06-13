package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.DocumentsExtraction;
import com.linkyoyo.reportaudit.info.DocumentsExtractionInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.DocumentsExtractionQuery;
import com.linkyoyo.reportaudit.repository.DocumentsExtractionRepository;
import com.linkyoyo.reportaudit.service.DocumentsExtractionService;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;

@Service
public class DocumentsExtractionServiceImpl
        extends AbstractCrudService<DocumentsExtraction, DocumentsExtractionInfo, Integer, DocumentsExtractionQuery>
        implements DocumentsExtractionService {

    @Autowired
    private DocumentsExtractionRepository documentsExtractionRepository;

    @Override
    protected JpaRepository<DocumentsExtraction, Integer> getRepository() {
        return documentsExtractionRepository;
    }

    @Override
    protected Integer getInfoId(DocumentsExtractionInfo info) {
        return info.getId();
    }

    @Override
    protected DocumentsExtraction createEntity() {
        return DocumentsExtraction.builder().build();
    }

    @Override
    public PageInfo<DocumentsExtraction> getDocumentsExtractionList(DocumentsExtractionQuery documentsExtractionQuery) {
        return getList(documentsExtractionQuery);
    }

    @Override
    public DocumentsExtractionInfo getDocumentsExtractionDetail(Integer id) {
        DocumentsExtraction documentsExtraction = getDetail(id);
        DocumentsExtractionInfo documentsExtractionInfo = new DocumentsExtractionInfo();
        if (Objects.nonNull(documentsExtraction))
            BeanUtils.copyProperties(documentsExtraction, documentsExtractionInfo);
        // TODO: 查询明细数据
        return documentsExtractionInfo;
    }
}
