package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.CheckResult;
import com.linkyoyo.reportaudit.info.CheckResultInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.CheckResultQuery;
import com.linkyoyo.reportaudit.repository.CheckResultRepository;
import com.linkyoyo.reportaudit.service.CheckResultService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;

@Service
public class CheckResultServiceImpl extends AbstractCrudServiceImpl<CheckResult, CheckResultInfo, Integer>
        implements CheckResultService {

    @Autowired
    private CheckResultRepository checkResultRepository;

    @Override
    protected JpaRepository<CheckResult, Integer> getRepository() {
        return checkResultRepository;
    }

    @Override
    protected CheckResult newEntity() {
        return CheckResult.builder().build();
    }

    @Override
    protected Integer getInfoId(CheckResultInfo info) {
        return info.getId();
    }

    @Override
    public PageInfo<CheckResult> getCheckResultList(CheckResultQuery checkResultQuery) {
        Pageable pageable = PageableUtil.build(checkResultQuery);
        return PageableUtil.info(checkResultRepository.findAll(CommonFunc.<CheckResult>getWhere(checkResultQuery), pageable));
    }

    @Override
    public CheckResultInfo getCheckResultDetail(Integer id) {
        entityManager.clear();
        CheckResult checkResult = checkResultRepository.findById(id).orElse(null);
        CheckResultInfo checkResultInfo = new CheckResultInfo();
        if (Objects.nonNull(checkResult))
           BeanUtils.copyProperties(checkResult, checkResultInfo);
        // TODO: 查询明细数据
        return checkResultInfo;
    }
}
