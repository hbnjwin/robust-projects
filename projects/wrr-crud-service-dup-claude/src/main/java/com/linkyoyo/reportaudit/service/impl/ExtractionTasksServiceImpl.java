package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.info.ExtractionTasksInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.ExtractionTasksQuery;
import com.linkyoyo.reportaudit.repository.ExtractionTasksRepository;
import com.linkyoyo.reportaudit.service.ExtractionTasksService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;
import com.linkyoyo.reportaudit.entity.ExtractionResult;
import com.linkyoyo.reportaudit.info.ExtractionResultInfo;
import com.linkyoyo.reportaudit.repository.ExtractionResultRepository;
import com.linkyoyo.reportaudit.entity.ExtractionTasksItems;
import com.linkyoyo.reportaudit.info.ExtractionTasksItemsInfo;
import com.linkyoyo.reportaudit.repository.ExtractionTasksItemsRepository;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.UUID;
import java.time.LocalDateTime;

@Service
public class ExtractionTasksServiceImpl extends AbstractCrudServiceImpl<ExtractionTasks, ExtractionTasksInfo, String>
        implements ExtractionTasksService {

    @Autowired
    private ExtractionTasksRepository extractionTasksRepository;

    @Autowired
    private ExtractionResultRepository extractionResultRepository;

    @Autowired
    private ExtractionTasksItemsRepository extractionTasksItemsRepository;

    // ---- AbstractCrudServiceImpl 抽象方法实现 ----

    @Override
    protected JpaRepository<ExtractionTasks, String> getRepository() {
        return extractionTasksRepository;
    }

    @Override
    protected ExtractionTasks newEntity() {
        return ExtractionTasks.builder().build();
    }

    @Override
    protected String getInfoId(ExtractionTasksInfo info) {
        return info.getId();
    }

    @Override
    protected void beforeCreate(ExtractionTasks entity, ExtractionTasksInfo info) {
        entity.setId(UUID.randomUUID().toString());
        entity.setCreatedAt(LocalDateTime.now());
        entity.setUpdatedAt(LocalDateTime.now());
    }

    @Override
    protected void beforeUpdate(ExtractionTasks entity, ExtractionTasksInfo info) {
        entity.setUpdatedAt(LocalDateTime.now());
    }

    @Override
    protected List<ChildTableHandler<ExtractionTasks, ExtractionTasksInfo, ?, ?>> getChildTableHandlers() {
        return Arrays.asList(
                ChildTableHandler.of(
                        extractionResultRepository,
                        "taskId",
                        ExtractionTasksInfo::getExtractionResultList,
                        () -> ExtractionResult.builder().build(),
                        (child, parent) -> child.setTaskId(parent.getId()),
                        parent -> parent.getId()
                ),
                ChildTableHandler.of(
                        extractionTasksItemsRepository,
                        "extractionTaskId",
                        ExtractionTasksInfo::getExtractionTasksItemsList,
                        () -> ExtractionTasksItems.builder().build(),
                        (child, parent) -> child.setExtractionTaskId(parent.getId()),
                        parent -> parent.getId()
                )
        );
    }

    // ---- 业务方法 ----

    @Override
    public PageInfo<ExtractionTasks> getExtractionTasksList(ExtractionTasksQuery extractionTasksQuery) {
        Pageable pageable = PageableUtil.build(extractionTasksQuery);
        return PageableUtil.info(extractionTasksRepository.findAll(CommonFunc.<ExtractionTasks>getWhere(extractionTasksQuery), pageable));
    }

    @Override
    public ExtractionTasks getExtractionTasksDetail(String id) {
        entityManager.clear();
        Optional<ExtractionTasks> optionalExtractionTasks = extractionTasksRepository.findById(id);
        if (optionalExtractionTasks.isPresent()) {
            return optionalExtractionTasks.get();
        }
        return null;
    }

    @Override
    public void markDeleted(String id) {
        ExtractionTasks extractionTasks = extractionTasksRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("未找到ID为 " + id + " 的抽取任务"));
        extractionTasks.setDelFlag(Boolean.TRUE);
        extractionTasks.setUpdatedAt(LocalDateTime.now());
        extractionTasksRepository.save(extractionTasks);
    }
}
