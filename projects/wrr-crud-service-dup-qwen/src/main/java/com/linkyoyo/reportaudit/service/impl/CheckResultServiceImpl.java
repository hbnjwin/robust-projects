package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.CheckResult;
import com.linkyoyo.reportaudit.info.CheckResultInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.CheckResultQuery;
import com.linkyoyo.reportaudit.repository.CheckResultRepository;
import com.linkyoyo.reportaudit.service.CheckResultService;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;

@Service
public class CheckResultServiceImpl
        extends AbstractCrudService<CheckResult, CheckResultInfo, Integer, CheckResultQuery>
        implements CheckResultService {

    @Autowired
    private CheckResultRepository checkResultRepository;

    @Override
    protected JpaRepository<CheckResult, Integer> getRepository() {
        return checkResultRepository;
    }

    @Override
    protected Integer getInfoId(CheckResultInfo info) {
        return info.getId();
    }

    @Override
    protected CheckResult createEntity() {
        return CheckResult.builder().build();
    }

    @Override
    public PageInfo<CheckResult> getCheckResultList(CheckResultQuery checkResultQuery) {
        return getList(checkResultQuery);
    }

    @Override
    public CheckResultInfo getCheckResultDetail(Integer id) {
        CheckResult checkResult = getDetail(id);
        CheckResultInfo checkResultInfo = new CheckResultInfo();
        if (Objects.nonNull(checkResult))
            BeanUtils.copyProperties(checkResult, checkResultInfo);
        // TODO: 查询明细数据
        return checkResultInfo;
    }
}
