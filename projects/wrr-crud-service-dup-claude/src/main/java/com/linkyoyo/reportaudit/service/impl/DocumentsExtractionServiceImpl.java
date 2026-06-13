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
import org.springframework.stereotype.Service;

import javax.persistence.EntityManager;
import java.util.Objects;

@Service
public class DocumentsExtractionServiceImpl implements DocumentsExtractionService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private DocumentsExtractionRepository documentsExtractionRepository;



    @Override
    public PageInfo<DocumentsExtraction> getDocumentsExtractionList(DocumentsExtractionQuery documentsExtractionQuery) {
        Pageable pageable = PageableUtil.build(documentsExtractionQuery);
        return PageableUtil.info(documentsExtractionRepository.findAll(CommonFunc.<DocumentsExtraction>getWhere(documentsExtractionQuery), pageable));
    }

    @Override
    public DocumentsExtraction createOrUpdate(DocumentsExtractionInfo documentsExtractionInfo) {
        if (Objects.isNull(documentsExtractionInfo.getId())) {
            DocumentsExtraction documentsExtraction = DocumentsExtraction.builder().build();
            BeanUtils.copyProperties(documentsExtractionInfo, documentsExtraction);
            documentsExtraction = documentsExtractionRepository.save(documentsExtraction);
            // TODO: 保存明细数据
            return documentsExtraction;
        } else {
            entityManager.clear();
            DocumentsExtraction documentsExtraction = documentsExtractionRepository.findById(documentsExtractionInfo.getId()).orElse(null);
            if (documentsExtraction != null) {
                BeanUtils.copyProperties(documentsExtractionInfo, documentsExtraction);
                documentsExtraction = documentsExtractionRepository.save(documentsExtraction);
            // TODO: 保存明细数据
            }
            return documentsExtraction;
        }
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
