package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.DocumentsExtraction;
import com.linkyoyo.reportaudit.info.DocumentsExtractionInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.DocumentsExtractionQuery;
import com.linkyoyo.reportaudit.repository.DocumentsExtractionRepository;
import com.linkyoyo.reportaudit.service.DocumentsExtractionService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;

@Service
public class DocumentsExtractionServiceImpl extends AbstractCrudServiceImpl<DocumentsExtraction, DocumentsExtractionInfo, Integer>
        implements DocumentsExtractionService {

    @Autowired
    private DocumentsExtractionRepository documentsExtractionRepository;

    @Override
    protected JpaRepository<DocumentsExtraction, Integer> getRepository() {
        return documentsExtractionRepository;
    }

    @Override
    protected DocumentsExtraction newEntity() {
        return DocumentsExtraction.builder().build();
    }

    @Override
    protected Integer getInfoId(DocumentsExtractionInfo info) {
        return info.getId();
    }

    @Override
    public PageInfo<DocumentsExtraction> getDocumentsExtractionList(DocumentsExtractionQuery documentsExtractionQuery) {
        Pageable pageable = PageableUtil.build(documentsExtractionQuery);
        return PageableUtil.info(documentsExtractionRepository.findAll(CommonFunc.<DocumentsExtraction>getWhere(documentsExtractionQuery), pageable));
    }

    @Override
    public DocumentsExtractionInfo getDocumentsExtractionDetail(Integer id) {
        entityManager.clear();
        DocumentsExtraction documentsExtraction = documentsExtractionRepository.findById(id).orElse(null);
        DocumentsExtractionInfo documentsExtractionInfo = new DocumentsExtractionInfo();
        if (Objects.nonNull(documentsExtraction))
           BeanUtils.copyProperties(documentsExtraction, documentsExtractionInfo);
        // TODO: 查询明细数据
        return documentsExtractionInfo;
    }
}
