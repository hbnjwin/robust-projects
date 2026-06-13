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
import java.util.List;
import java.util.stream.Collectors;
import com.github.wenhao.jpa.Specifications;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import javax.persistence.EntityManager;
import java.util.Objects;
import java.util.UUID;
import java.util.Optional;
import java.time.LocalDateTime;
import java.time.LocalDateTime;

@Service
public class ExtractionTasksServiceImpl implements ExtractionTasksService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private ExtractionTasksRepository extractionTasksRepository;

    @Autowired
    private ExtractionResultRepository extractionResultRepository;
    @Autowired
    private ExtractionTasksItemsRepository extractionTasksItemsRepository;

    @Override
    public PageInfo<ExtractionTasks> getExtractionTasksList(ExtractionTasksQuery extractionTasksQuery) {
        Pageable pageable = PageableUtil.build(extractionTasksQuery);
        return PageableUtil.info(extractionTasksRepository.findAll(CommonFunc.<ExtractionTasks>getWhere(extractionTasksQuery), pageable));
    }

    @Override
    public ExtractionTasks createOrUpdate(ExtractionTasksInfo extractionTasksInfo) {
        if (Objects.isNull(extractionTasksInfo.getId())) {
            ExtractionTasks extractionTasks = ExtractionTasks.builder().build();
            BeanUtils.copyProperties(extractionTasksInfo, extractionTasks);
            // 为新任务生成UUID作为ID
            extractionTasks.setId(UUID.randomUUID().toString());
            // 设置创建时间
            extractionTasks.setCreatedAt(LocalDateTime.now());
            extractionTasks.setUpdatedAt(LocalDateTime.now());
            extractionTasks = extractionTasksRepository.save(extractionTasks);

            // 保存ExtractionResult明细数据
            if (Objects.nonNull(extractionTasksInfo.getExtractionResultList())) {
                // 先删除原有的ExtractionResult数据
                List<ExtractionResult> existingExtractionResultList = extractionResultRepository.findAll(
                    Specifications.<ExtractionResult>and()
                        .eq("taskId", extractionTasks.getId())
                        .build()
                );
                extractionResultRepository.deleteAll(existingExtractionResultList);

                // 保存新的ExtractionResult数据
                List<ExtractionResultInfo> extractionResultList = extractionTasksInfo.getExtractionResultList();
                for (ExtractionResultInfo extractionResultInfo : extractionResultList) {
                    ExtractionResult extractionResult = ExtractionResult.builder().build();
                    BeanUtils.copyProperties(extractionResultInfo, extractionResult);
                    extractionResult.setTaskId(extractionTasks.getId());
                    extractionResultRepository.save(extractionResult);
                }
            }
            // 保存ExtractionTasksItems明细数据
            if (Objects.nonNull(extractionTasksInfo.getExtractionTasksItemsList())) {
                // 先删除原有的ExtractionTasksItems数据
                List<ExtractionTasksItems> existingExtractionTasksItemsList = extractionTasksItemsRepository.findAll(
                    Specifications.<ExtractionTasksItems>and()
                        .eq("extractionTaskId", extractionTasks.getId())
                        .build()
                );
                extractionTasksItemsRepository.deleteAll(existingExtractionTasksItemsList);

                // 保存新的ExtractionTasksItems数据
                List<ExtractionTasksItemsInfo> extractionTasksItemsList = extractionTasksInfo.getExtractionTasksItemsList();
                for (ExtractionTasksItemsInfo extractionTasksItemsInfo : extractionTasksItemsList) {
                    ExtractionTasksItems extractionTasksItems = ExtractionTasksItems.builder().build();
                    BeanUtils.copyProperties(extractionTasksItemsInfo, extractionTasksItems);
                    extractionTasksItems.setExtractionTaskId(extractionTasks.getId());
                    extractionTasksItemsRepository.save(extractionTasksItems);
                }
            }
            return extractionTasks;
        } else {
            entityManager.clear();
            Optional<ExtractionTasks> optionalExtractionTasks = extractionTasksRepository.findById(extractionTasksInfo.getId());
            if (optionalExtractionTasks.isPresent()) {
                ExtractionTasks extractionTasks = optionalExtractionTasks.get();
                BeanUtils.copyProperties(extractionTasksInfo, extractionTasks);
                // 更新时间
                extractionTasks.setUpdatedAt(LocalDateTime.now());
                extractionTasks = extractionTasksRepository.save(extractionTasks);

                // 保存ExtractionResult明细数据
                if (Objects.nonNull(extractionTasksInfo.getExtractionResultList())) {
                    // 先删除原有的ExtractionResult数据
                    List<ExtractionResult> existingExtractionResultList = extractionResultRepository.findAll(
                        Specifications.<ExtractionResult>and()
                            .eq("taskId", extractionTasks.getId())
                            .build()
                    );
                    extractionResultRepository.deleteAll(existingExtractionResultList);

                    // 保存新的ExtractionResult数据
                    List<ExtractionResultInfo> extractionResultList = extractionTasksInfo.getExtractionResultList();
                    for (ExtractionResultInfo extractionResultInfo : extractionResultList) {
                        ExtractionResult extractionResult = ExtractionResult.builder().build();
                        BeanUtils.copyProperties(extractionResultInfo, extractionResult);
                        extractionResult.setTaskId(extractionTasks.getId());
                        extractionResultRepository.save(extractionResult);
                    }
                }
                // 保存ExtractionTasksItems明细数据
                if (Objects.nonNull(extractionTasksInfo.getExtractionTasksItemsList())) {
                    // 先删除原有的ExtractionTasksItems数据
                    List<ExtractionTasksItems> existingExtractionTasksItemsList = extractionTasksItemsRepository.findAll(
                        Specifications.<ExtractionTasksItems>and()
                            .eq("extractionTaskId", extractionTasks.getId())
                            .build()
                    );
                    extractionTasksItemsRepository.deleteAll(existingExtractionTasksItemsList);

                    // 保存新的ExtractionTasksItems数据
                    List<ExtractionTasksItemsInfo> extractionTasksItemsList = extractionTasksInfo.getExtractionTasksItemsList();
                    for (ExtractionTasksItemsInfo extractionTasksItemsInfo : extractionTasksItemsList) {
                        ExtractionTasksItems extractionTasksItems = ExtractionTasksItems.builder().build();
                        BeanUtils.copyProperties(extractionTasksItemsInfo, extractionTasksItems);
                        extractionTasksItems.setExtractionTaskId(extractionTasks.getId());
                        extractionTasksItemsRepository.save(extractionTasksItems);
                    }
                }
                return extractionTasks;
            }
            return null;
        }
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
