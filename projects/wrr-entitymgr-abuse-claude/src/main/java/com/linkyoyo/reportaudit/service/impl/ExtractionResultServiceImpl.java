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
import org.springframework.stereotype.Service;

import javax.persistence.EntityManager;
import java.util.Objects;

@Service
public class ExtractionResultServiceImpl implements ExtractionResultService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private ExtractionResultRepository extractionResultRepository;



    @Override
    public PageInfo<ExtractionResult> getExtractionResultList(ExtractionResultQuery extractionResultQuery) {
        Pageable pageable = PageableUtil.build(extractionResultQuery);
        return PageableUtil.info(extractionResultRepository.findAll(CommonFunc.<ExtractionResult>getWhere(extractionResultQuery), pageable));
    }

    @Override
    public ExtractionResult createOrUpdate(ExtractionResultInfo extractionResultInfo) {
        if (Objects.isNull(extractionResultInfo.getId())) {
            ExtractionResult extractionResult = ExtractionResult.builder().build();
            BeanUtils.copyProperties(extractionResultInfo, extractionResult);
            extractionResult = extractionResultRepository.save(extractionResult);
            // TODO: 保存明细数据
            return extractionResult;
        } else {
            entityManager.clear();
            ExtractionResult extractionResult = extractionResultRepository.findById(extractionResultInfo.getId()).orElse(null);
            if (extractionResult != null) {
                BeanUtils.copyProperties(extractionResultInfo, extractionResult);
                extractionResult = extractionResultRepository.save(extractionResult);
            // TODO: 保存明细数据
            }
            return extractionResult;
        }
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
