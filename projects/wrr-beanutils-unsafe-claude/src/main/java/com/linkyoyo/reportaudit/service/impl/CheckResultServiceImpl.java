package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.CheckResult;
import com.linkyoyo.reportaudit.info.CheckResultInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.CheckResultQuery;
import com.linkyoyo.reportaudit.repository.CheckResultRepository;
import com.linkyoyo.reportaudit.service.CheckResultService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;


import com.linkyoyo.reportaudit.mapper.CheckResultMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import javax.persistence.EntityManager;
import java.util.Objects;

@Service
public class CheckResultServiceImpl implements CheckResultService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private CheckResultRepository checkResultRepository;

    @Autowired
    private CheckResultMapper checkResultMapper;



    @Override
    public PageInfo<CheckResult> getCheckResultList(CheckResultQuery checkResultQuery) {
        Pageable pageable = PageableUtil.build(checkResultQuery);
        return PageableUtil.info(checkResultRepository.findAll(CommonFunc.<CheckResult>getWhere(checkResultQuery), pageable));
    }

    @Override
    public CheckResult createOrUpdate(CheckResultInfo checkResultInfo) {
        if (Objects.isNull(checkResultInfo.getId())) {
            CheckResult checkResult = checkResultMapper.toEntity(checkResultInfo);
            checkResult = checkResultRepository.save(checkResult);
            // TODO: 保存明细数据
            return checkResult;
        } else {
            entityManager.clear();
            CheckResult checkResult = checkResultRepository.findById(checkResultInfo.getId()).orElse(null);
            if (checkResult != null) {
                checkResultMapper.updateEntity(checkResultInfo, checkResult);
                checkResult = checkResultRepository.save(checkResult);
            // TODO: 保存明细数据
            }
            return checkResult;
        }
    }

    @Override
    public CheckResultInfo getCheckResultDetail(Integer id) {
        entityManager.clear();
        CheckResult checkResult = checkResultRepository.findById(id).orElse(null);
        CheckResultInfo checkResultInfo = Objects.nonNull(checkResult)
            ? checkResultMapper.toInfo(checkResult)
            : new CheckResultInfo();
        // TODO: 查询明细数据
        return checkResultInfo;
    }
}
