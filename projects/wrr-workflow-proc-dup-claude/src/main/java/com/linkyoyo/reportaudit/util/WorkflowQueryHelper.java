package com.linkyoyo.reportaudit.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.CheckItems;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.querydsl.jpa.impl.JPAQueryFactory;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.annotation.PostConstruct;
import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import java.util.ArrayList;
import java.util.List;

import static com.linkyoyo.reportaudit.entity.QExtractionRules.extractionRules;
import static com.linkyoyo.reportaudit.entity.QCheckItems.checkItems;
import static com.linkyoyo.reportaudit.entity.QSysParaset.sysParaset;

/**
 * 工作流数据查询Helper
 * 集中管理三个工作流处理器共用的数据查询方法，消除重复代码
 */
@Slf4j
@Component
public class WorkflowQueryHelper {

    @PersistenceContext
    private EntityManager entityManager;

    private JPAQueryFactory queryFactory;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @PostConstruct
    public void init() {
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    public JPAQueryFactory getQueryFactory() {
        return queryFactory;
    }

    public ObjectMapper getObjectMapper() {
        return objectMapper;
    }

    /**
     * 解析选中项目字符串为ID列表
     * 支持多种格式：
     * 1. JSON数组格式：[1, 3, 5] 或 [1,3,5]
     * 2. 逗号分隔：1,3,5 或 1, 3, 5
     * 3. 单个数字：5
     */
    public List<Integer> parseSelectedItems(String selectedItems) {
        List<Integer> itemIds = new ArrayList<>();
        if (StringUtils.hasText(selectedItems)) {
            try {
                String cleanedItems = selectedItems.trim()
                    .replaceAll("^\\[", "")
                    .replaceAll("\\]$", "")
                    .replaceAll("\\s+", "");

                if (StringUtils.hasText(cleanedItems)) {
                    String[] items = cleanedItems.split(",");
                    for (String item : items) {
                        if (StringUtils.hasText(item)) {
                            itemIds.add(Integer.parseInt(item.trim()));
                        }
                    }
                }

                log.debug("解析选中项目成功: selectedItems={} -> itemIds={}", selectedItems, itemIds);
            } catch (Exception e) {
                log.error("解析选中项目失败: selectedItems={}, error={}", selectedItems, e.getMessage());
            }
        }
        return itemIds;
    }

    /**
     * 获取抽取规则（不排序）
     */
    public List<ExtractionRules> getExtractionRules(List<Integer> ruleIds) {
        if (ruleIds.isEmpty()) {
            return new ArrayList<>();
        }

        return queryFactory.selectFrom(extractionRules)
                .where(extractionRules.id.in(ruleIds)
                        .and(extractionRules.delFlag.isNull().or(extractionRules.delFlag.eq(false))))
                .fetch();
    }

    /**
     * 获取抽取规则（按优先级降序、ID升序排列）
     */
    public List<ExtractionRules> getExtractionRulesOrdered(List<Integer> ruleIds) {
        if (ruleIds.isEmpty()) {
            return new ArrayList<>();
        }

        return queryFactory.selectFrom(extractionRules)
                .where(extractionRules.id.in(ruleIds)
                        .and(extractionRules.delFlag.isNull().or(extractionRules.delFlag.eq(false))))
                .orderBy(extractionRules.priority.desc(), extractionRules.id.asc())
                .fetch();
    }

    /**
     * 获取检查项（不排序）
     */
    public List<CheckItems> getCheckItems(List<Integer> checkIds) {
        if (checkIds.isEmpty()) {
            return new ArrayList<>();
        }

        return queryFactory.selectFrom(checkItems)
                .where(checkItems.id.in(checkIds)
                        .and(checkItems.delFlag.isNull().or(checkItems.delFlag.eq(false))))
                .fetch();
    }

    /**
     * 获取检查项（按sequence升序、ID升序排列）
     */
    public List<CheckItems> getCheckItemsOrdered(List<Integer> checkIds) {
        if (checkIds.isEmpty()) {
            return new ArrayList<>();
        }

        return queryFactory.selectFrom(checkItems)
                .where(checkItems.id.in(checkIds)
                        .and(checkItems.delFlag.isNull().or(checkItems.delFlag.eq(false))))
                .orderBy(checkItems.sequence.asc(), checkItems.id.asc())
                .fetch();
    }

    /**
     * 从sysParaset表获取默认工作流配置
     */
    public WorkflowConfig getDefaultWorkflowConfig() {
        try {
            String configJson = queryFactory
                .select(sysParaset.agentPara)
                .from(sysParaset)
                .fetchFirst();

            if (configJson == null || configJson.trim().isEmpty()) {
                throw new RuntimeException("未找到工作流配置数据");
            }

            return objectMapper.readValue(configJson, WorkflowConfig.class);
        } catch (Exception e) {
            log.error("获取工作流配置失败: {}", e.getMessage());
            throw new RuntimeException("无法获取工作流配置", e);
        }
    }
}
