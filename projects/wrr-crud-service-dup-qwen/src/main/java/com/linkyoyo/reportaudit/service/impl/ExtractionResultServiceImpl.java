package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.ExtractionResult;
import com.linkyoyo.reportaudit.info.ExtractionResultInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.ExtractionResultQuery;
import com.linkyoyo.reportaudit.repository.ExtractionResultRepository;
import com.linkyoyo.reportaudit.service.ExtractionResultService;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;

@Service
public class ExtractionResultServiceImpl
        extends AbstractCrudService<ExtractionResult, ExtractionResultInfo, Integer, ExtractionResultQuery>
        implements ExtractionResultService {

    @Autowired
    private ExtractionResultRepository extractionResultRepository;

    @Override
    protected JpaRepository<ExtractionResult, Integer> getRepository() {
        return extractionResultRepository;
    }

    @Override
    protected Integer getInfoId(ExtractionResultInfo info) {
        return info.getId();
    }

    @Override
    protected ExtractionResult createEntity() {
        return ExtractionResult.builder().build();
    }

    @Override
    public PageInfo<ExtractionResult> getExtractionResultList(ExtractionResultQuery extractionResultQuery) {
        return getList(extractionResultQuery);
    }

    @Override
    public ExtractionResultInfo getExtractionResultDetail(Integer id) {
        ExtractionResult extractionResult = getDetail(id);
        ExtractionResultInfo extractionResultInfo = new ExtractionResultInfo();
        if (Objects.nonNull(extractionResult))
            BeanUtils.copyProperties(extractionResult, extractionResultInfo);
        // TODO: 查询明细数据
        return extractionResultInfo;
    }
}
