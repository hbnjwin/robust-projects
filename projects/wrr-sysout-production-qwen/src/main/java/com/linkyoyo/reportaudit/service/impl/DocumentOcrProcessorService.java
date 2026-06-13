package com.linkyoyo.reportaudit.service.impl;

import cn.hutool.core.collection.CollectionUtil;
import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.entity.DocumentsToc;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.repository.DocumentsRepository;
import com.linkyoyo.reportaudit.repository.DocumentsTocRepository;
import com.linkyoyo.reportaudit.repository.ExtractionTasksRepository;
import com.linkyoyo.reportaudit.repository.ExtractionRulesRepository;
import com.linkyoyo.reportaudit.service.TextinService;
import com.linkyoyo.reportaudit.util.RuleClassUtils;
import com.linkyoyo.reportaudit.entity.RuleClass;
import com.querydsl.jpa.impl.JPAQueryFactory;
import com.linkyoyo.reportaudit.entity.QExtractionTasks;
import com.linkyoyo.reportaudit.entity.QExtractionRules;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import javax.persistence.EntityManager;
import java.time.LocalDateTime;
import java.math.BigDecimal;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

/**
 * 文档OCR处理服务
 * 专门处理异步OCR任务
 */
@Service
public class DocumentOcrProcessorService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private DocumentsRepository documentsRepository;

    @Autowired
    private DocumentsTocRepository documentsTocRepository;

    @Autowired
    private ExtractionTasksRepository extractionTasksRepository;

    @Autowired
    private ExtractionRulesRepository extractionRulesRepository;

    @Autowired
    private TextinService textinService;

    private JPAQueryFactory queryFactory;

    @Autowired
    public void setEntityManager(EntityManager entityManager) {
        this.entityManager = entityManager;
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    /**
     * 异步处理OCR和后续操作
     * 
     * @param originalFile 原始文件
     * @param documentId 文档ID
     * @param currentUser 当前用户信息
     */
    @Async
    public void processOcrAsync(java.io.File originalFile, Integer documentId, com.linkyoyo.reportaudit.entity.SysOperator currentUser) {
        System.out.println("开始异步OCR处理，文档ID: " + documentId);
        
        try {
            // 重新查询文档对象，确保获取最新状态
            Documents document = documentsRepository.findById(documentId).orElse(null);
            if (document == null) {
                System.err.println("异步OCR处理失败：找不到文档ID " + documentId);
                return;
            }

            System.out.println("执行OCR处理...");
            // 执行OCR处理
            textinService.uploadBySysParasetOcr(originalFile, document);

            // 处理Markdown内容的章节整理
            String mdContent = document.getMdContent();
            if (mdContent != null && !mdContent.trim().isEmpty()) {
                try {
                    System.out.println("处理Markdown内容和章节整理...");
                    // 调用章节处理方法
                    Map<String, Object> processResult = com.linkyoyo.reportaudit.util.ProcessRealFile.processMarkdownContent(mdContent);

                    // 更新处理后的Markdown内容
                    String cleanedMarkdown = (String) processResult.get("cleanedMarkdown");
                    if (cleanedMarkdown != null) {
                        document.setMdContent(cleanedMarkdown);
                    }

                    // 处理TOC数据并保存到DocumentsToc表
                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> tocList = (List<Map<String, Object>>) processResult.get("tableOfContents");
                    if (tocList != null && !tocList.isEmpty()) {
                        processTocData(document.getId().intValue(), tocList);
                    }

                } catch (Exception e) {
                    System.err.println("章节处理失败: " + e.getMessage());
                    e.printStackTrace();
                }
            }

            // 更新处理状态为OCR_COMPLETED，并保存mdContent
            document.setProcessingStatus("OCR_COMPLETED");
            document.setUpdatedAt(java.time.LocalDateTime.now());
            documentsRepository.save(document);

            System.out.println("创建抽取任务...");
            // 增加创建extractionTasks的方法
            createExtractionTasks(document.getId().longValue(), currentUser);

            System.out.println("异步OCR处理完成，文档ID: " + documentId);

        } catch (Exception e) {
            System.err.println("异步OCR处理失败，文档ID: " + documentId + ", 错误: " + e.getMessage());
            e.printStackTrace();
            
            // 更新处理状态为OCR_FAILED
            try {
                Documents document = documentsRepository.findById(documentId).orElse(null);
                if (document != null) {
                    document.setProcessingStatus("OCR_FAILED");
                    document.setProcessingError(e.getMessage());
                    document.setUpdatedAt(java.time.LocalDateTime.now());
                    documentsRepository.save(document);
                }
            } catch (Exception saveException) {
                System.err.println("保存OCR失败状态时出错: " + saveException.getMessage());
            }
        }
    }

    /**
     * 处理TOC数据并保存到DocumentsToc表
     *
     * @param docId   文档ID
     * @param tocList TOC数据列表
     */
    private void processTocData(Integer docId, List<Map<String, Object>> tocList) {
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
            toc.setCreatedAt(java.time.LocalDateTime.now());
            toc.setUpdatedAt(java.time.LocalDateTime.now());

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
    private void createExtractionTasks(Long docId, com.linkyoyo.reportaudit.entity.SysOperator currentUser) {
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
                    .orderBy(qExtractionRules.id.asc())  // 在数据库层排序
                    .fetch();

            // CollectionUtil.sort(activeRules, Comparator.comparing(ExtractionRules::getId));

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
