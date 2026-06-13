package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.ExtractionResult;
import com.linkyoyo.reportaudit.info.ExtractionResultInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.ExtractionResultQuery;
import com.linkyoyo.reportaudit.repository.ExtractionResultRepository;
import com.linkyoyo.reportaudit.service.ExtractionResultService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;

@Service
public class ExtractionResultServiceImpl extends AbstractCrudServiceImpl<ExtractionResult, ExtractionResultInfo, Integer>
        implements ExtractionResultService {

    @Autowired
    private ExtractionResultRepository extractionResultRepository;

    @Override
    protected JpaRepository<ExtractionResult, Integer> getRepository() {
        return extractionResultRepository;
    }

    @Override
    protected ExtractionResult newEntity() {
        return ExtractionResult.builder().build();
    }

    @Override
    protected Integer getInfoId(ExtractionResultInfo info) {
        return info.getId();
    }

    @Override
    public PageInfo<ExtractionResult> getExtractionResultList(ExtractionResultQuery extractionResultQuery) {
        Pageable pageable = PageableUtil.build(extractionResultQuery);
        return PageableUtil.info(extractionResultRepository.findAll(CommonFunc.<ExtractionResult>getWhere(extractionResultQuery), pageable));
    }

    @Override
    public ExtractionResultInfo getExtractionResultDetail(Integer id) {
        entityManager.clear();
        ExtractionResult extractionResult = extractionResultRepository.findById(id).orElse(null);
        ExtractionResultInfo extractionResultInfo = new ExtractionResultInfo();
        if (Objects.nonNull(extractionResult))
           BeanUtils.copyProperties(extractionResult, extractionResultInfo);
        // TODO: 查询明细数据
        return extractionResultInfo;
    }
}
