package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.DocumentsToc;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.QExtractionRules;
import com.linkyoyo.reportaudit.entity.QExtractionTasks;
import com.linkyoyo.reportaudit.entity.RuleClass;
import com.linkyoyo.reportaudit.entity.SysOperator;
import com.linkyoyo.reportaudit.repository.DocumentsTocRepository;
import com.linkyoyo.reportaudit.repository.ExtractionTasksRepository;
import com.linkyoyo.reportaudit.util.RuleClassUtils;
import com.querydsl.jpa.impl.JPAQueryFactory;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.persistence.EntityManager;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 文档处理共享服务
 * 提供 processTocData 和 createExtractionTasks 的共享实现，
 * 消除 DocumentsServiceImpl 和 DocumentOcrProcessorService 之间的代码重复。
 */
@Component
public class ExtractionSharedService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private DocumentsTocRepository documentsTocRepository;

    @Autowired
    private ExtractionTasksRepository extractionTasksRepository;

    private JPAQueryFactory queryFactory;

    @Autowired
    public void setEntityManager(EntityManager entityManager) {
        this.entityManager = entityManager;
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    /**
     * 处理TOC数据并保存到DocumentsToc表
     *
     * @param docId   文档ID
     * @param tocList TOC数据列表
     */
    public void processTocData(Integer docId, List<Map<String, Object>> tocList) {
        // 先删除该文档的旧TOC记录
        documentsTocRepository.deleteByDocId(docId);

        // 保存新的TOC记录
        for (int i = 0; i < tocList.size(); i++) {
            Map<String, Object> tocItem = tocList.get(i);
            DocumentsToc toc = new DocumentsToc();

            toc.setDocId(docId);

            // 解析章节标题，提取编号和标题
            String title = (String) tocItem.get("title");
            if (title != null) {
                // section_title保留优化后的完整格式（包含##标记）
                toc.setSectionTitle(title);

                // 移除Markdown标记符号用于提取编号
                String cleanTitle = title.replaceAll("^#+\\s*", "").trim();

                // 提取章节编号
                if (cleanTitle.matches("^[0-9]+(?:\\.[0-9]+)*[\\.．].*")) {
                    // 找到第一个点或中文句号后的空格位置
                    int spaceIndex = -1;
                    for (int idx = 0; idx < cleanTitle.length(); idx++) {
                        char c = cleanTitle.charAt(idx);
                        if ((c == '.' || c == '．') && idx + 1 < cleanTitle.length() && cleanTitle.charAt(idx + 1) == ' ') {
                            spaceIndex = idx + 1;
                            break;
                        }
                    }

                    if (spaceIndex > 0) {
                        String sectionNumber = cleanTitle.substring(0, spaceIndex - 1);
                        toc.setSectionNumber(sectionNumber);
                    } else {
                        // 如果没有找到空格，按原逻辑处理
                        int dotIndex = cleanTitle.indexOf('.');
                        if (dotIndex == -1) dotIndex = cleanTitle.indexOf('．');

                        if (dotIndex > 0) {
                            String sectionNumber = cleanTitle.substring(0, dotIndex);
                            toc.setSectionNumber(sectionNumber);
                        } else {
                            toc.setSectionNumber("");
                        }
                    }
                } else {
                    toc.setSectionNumber("");
                }

                // 计算章节级别
                int level = (int) title.chars().takeWhile(c -> c == '#').count();
                toc.setLevel(level);
            }

            toc.setSectionContent((String) tocItem.get("content"));
            toc.setDisplayOrder(i + 1);
            toc.setOriginalLine((String) tocItem.get("originalLine"));

            Integer lineNumber = (Integer) tocItem.get("lineNumber");
            if (lineNumber != null) {
                toc.setLineNumber(lineNumber);
            }

            toc.setType("NUMBERED");
            toc.setCreatedAt(LocalDateTime.now());
            toc.setUpdatedAt(LocalDateTime.now());

            documentsTocRepository.save(toc);
        }
    }

    /**
     * 创建抽取任务
     * 使用QueryDSL查询，判断任务表中original_doc_id是否存在此docId
     * 如果不存在则新增抽取任务，selectedItems从extraction_rules表获取
     *
     * @param docId 文档ID
     * @param currentUser 当前用户信息
     */
    public void createExtractionTasks(Long docId, SysOperator currentUser) {
        try {
            // 清理EntityManager缓存，确保获取最新数据
            entityManager.clear();

            QExtractionTasks qExtractionTasks = QExtractionTasks.extractionTasks;
            QExtractionRules qExtractionRules = QExtractionRules.extractionRules;

            // 查询是否已存在该文档的抽取任务
            ExtractionTasks existingTask = queryFactory
                    .selectFrom(qExtractionTasks)
                    .where(qExtractionTasks.originalDocId.eq(docId))
                    .fetchOne();

            if (existingTask != null) {
                System.out.println("文档ID " + docId + " 的抽取任务已存在，跳过创建");
                return;
            }

            // 获取用户规则分类
            RuleClass ruleClass = RuleClassUtils.getRuleClass(currentUser);

            // 查询未删除的抽取规则，根据用户规则分类过滤
            com.querydsl.core.types.dsl.BooleanExpression whereCondition = qExtractionRules.delFlag.isNull()
                    .or(qExtractionRules.delFlag.eq(false));

            // 如果获取到规则分类，添加 classId 条件
            if (ruleClass != null && ruleClass.getId() != null) {
                whereCondition = whereCondition.and(qExtractionRules.classId.eq(ruleClass.getId()));
                System.out.println("根据用户规则分类过滤抽取规则: classId=" + ruleClass.getId() +
                    ", className=" + ruleClass.getClassName());
            }

            List<ExtractionRules> activeRules = queryFactory
                    .selectFrom(qExtractionRules)
                    .where(whereCondition)
                    .orderBy(qExtractionRules.id.asc())
                    .fetch();

            if (activeRules.isEmpty()) {
                System.out.println("没有找到有效的抽取规则，跳过创建抽取任务。用户规则分类: " +
                    (ruleClass != null ? ruleClass.getClassName() : "未获取到"));
                return;
            }

            // 构建selectedItems JSON字符串
            String selectedItems = "[" +
                    activeRules.stream()
                            .map(rule -> rule.getId().toString())
                            .collect(Collectors.joining(",")) +
                    "]";

            // 创建新的抽取任务
            ExtractionTasks newTask = ExtractionTasks.builder()
                    .id(UUID.randomUUID().toString())
                    .title("文档抽取任务")
                    .description("对原始文档进行数据抽取分析")
                    .status("queued")
                    .progress(BigDecimal.ZERO)
                    .originalDocId(docId)
                    .selectedItems(selectedItems)
                    .taskType("document_extraction")
                    .priority(1)
                    .maxRetries(3)
                    .retryCount(0)
                    .createdAt(LocalDateTime.now())
                    .updatedAt(LocalDateTime.now())
                    // 填充用户信息
                    .creater(currentUser.getId())
                    .deptId(currentUser.getDeptId())
                    .operatorCode(currentUser.getOperatorCode())
                    .build();

            // 保存抽取任务
            extractionTasksRepository.save(newTask);

            System.out.println("成功为文档ID " + docId + " 创建抽取任务，任务ID: " + newTask.getId() +
                    ", 包含 " + activeRules.size() + " 个抽取规则");

        } catch (Exception e) {
            System.err.println("创建抽取任务失败，文档ID: " + docId + ", 错误: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
