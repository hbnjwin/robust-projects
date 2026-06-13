package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.info.ExtractionTasksInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.ExtractionTasksQuery;
import com.linkyoyo.reportaudit.repository.ExtractionTasksRepository;
import com.linkyoyo.reportaudit.service.ExtractionTasksService;
import com.linkyoyo.reportaudit.entity.ExtractionResult;
import com.linkyoyo.reportaudit.repository.ExtractionResultRepository;
import com.linkyoyo.reportaudit.entity.ExtractionTasksItems;
import com.linkyoyo.reportaudit.repository.ExtractionTasksItemsRepository;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.UUID;

@Service
public class ExtractionTasksServiceImpl
        extends AbstractCrudService<ExtractionTasks, ExtractionTasksInfo, String, ExtractionTasksQuery>
        implements ExtractionTasksService {

    @Autowired
    private ExtractionTasksRepository extractionTasksRepository;

    @Autowired
    private ExtractionResultRepository extractionResultRepository;

    @Autowired
    private ExtractionTasksItemsRepository extractionTasksItemsRepository;

    @Override
    protected JpaRepository<ExtractionTasks, String> getRepository() {
        return extractionTasksRepository;
    }

    @Override
    protected String getInfoId(ExtractionTasksInfo info) {
        return info.getId();
    }

    @Override
    protected ExtractionTasks createEntity() {
        return ExtractionTasks.builder().build();
    }

    @Override
    protected void beforeCreate(ExtractionTasksInfo info, ExtractionTasks entity) {
        entity.setId(UUID.randomUUID().toString());
        entity.setCreatedAt(LocalDateTime.now());
        entity.setUpdatedAt(LocalDateTime.now());
    }

    @Override
    protected void beforeUpdate(ExtractionTasksInfo info, ExtractionTasks entity) {
        entity.setUpdatedAt(LocalDateTime.now());
    }

    @Override
    protected void saveChildTables(ExtractionTasksInfo info, ExtractionTasks entity) {
        // Child 1: ExtractionResult (FK: taskId)
        ChildTableUtils.saveChildTable(
                extractionResultRepository,
                entity.getId(),
                "taskId",
                info.getExtractionResultList(),
                ExtractionResult.builder()::build,
                (childInfo, child) -> BeanUtils.copyProperties(childInfo, child),
                (child, parentId) -> child.setTaskId(parentId));

        // Child 2: ExtractionTasksItems (FK: extractionTaskId)
        ChildTableUtils.saveChildTable(
                extractionTasksItemsRepository,
                entity.getId(),
                "extractionTaskId",
                info.getExtractionTasksItemsList(),
                ExtractionTasksItems.builder()::build,
                (childInfo, child) -> BeanUtils.copyProperties(childInfo, child),
                (child, parentId) -> child.setExtractionTaskId(parentId));
    }

    @Override
    public PageInfo<ExtractionTasks> getExtractionTasksList(ExtractionTasksQuery extractionTasksQuery) {
        return getList(extractionTasksQuery);
    }

    @Override
    public ExtractionTasks getExtractionTasksDetail(String id) {
        return getDetail(id);
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
