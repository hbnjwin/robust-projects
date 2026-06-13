package com.linkyoyo.reportaudit.service.impl;

import com.github.wenhao.jpa.PredicateBuilder;
import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.info.DocumentsCheckItemsInfo;
import com.linkyoyo.reportaudit.info.DocumentsExtractionInfo;
import com.linkyoyo.reportaudit.info.DocumentsInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.DocumentsQuery;
import com.linkyoyo.reportaudit.repository.DocumentsRepository;
import com.linkyoyo.reportaudit.service.DocumentsService;
import com.linkyoyo.reportaudit.service.TextinService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;
import com.linkyoyo.reportaudit.entity.DocumentsToc;
import com.linkyoyo.reportaudit.info.DocumentsTocInfo;
import com.linkyoyo.reportaudit.repository.DocumentsTocRepository;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.repository.ExtractionTasksRepository;
import com.linkyoyo.reportaudit.repository.ExtractionRulesRepository;
import com.linkyoyo.reportaudit.entity.DocumentsExtraction;
import com.linkyoyo.reportaudit.entity.DocumentsCheckItems;
import com.linkyoyo.reportaudit.repository.DocumentsExtractionRepository;
import com.linkyoyo.reportaudit.repository.DocumentsCheckItemsRepository;
import com.linkyoyo.reportaudit.repository.ProjectInfoRepository;
import com.linkyoyo.reportaudit.entity.ProjectInfo;
import com.linkyoyo.reportaudit.info.ProjectInfoInfo;
import com.linkyoyo.reportaudit.util.ProcessRealFile;
import com.querydsl.jpa.impl.JPAQueryFactory;
import com.linkyoyo.reportaudit.entity.QExtractionTasks;
import com.linkyoyo.reportaudit.entity.QExtractionRules;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.UUID;
import java.time.LocalDateTime;
import java.math.BigDecimal;

import com.github.wenhao.jpa.Specifications;

import com.linkyoyo.reportaudit.util.SysUserUtils;
import com.linkyoyo.reportaudit.util.RuleClassUtils;
import com.linkyoyo.reportaudit.entity.RuleClass;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Pageable;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import javax.persistence.EntityManager;
import org.springframework.transaction.annotation.Transactional;
import java.util.Objects;

@Service
@Slf4j
public class DocumentsServiceImpl implements DocumentsService {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    public void setEntityManager(EntityManager entityManager) {
        this.entityManager = entityManager;
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    @Autowired
    private DocumentsRepository documentsRepository;

    @Autowired
    private DocumentsTocRepository documentsTocRepository;

    @Autowired
    private ExtractionTasksRepository extractionTasksRepository;

    @Autowired
    private ExtractionRulesRepository extractionRulesRepository;

    @Autowired
    private DocumentsExtractionRepository documentsExtractionRepository;

    @Autowired
    private DocumentsCheckItemsRepository documentsCheckItemsRepository;

    @Autowired
    private ProjectInfoRepository projectInfoRepository;

    @Autowired
    private TextinService textinService;

    @Autowired
    private DocumentOcrProcessorService documentOcrProcessorService;

    private JPAQueryFactory queryFactory;

    @Value("${paraSet.uploadPath:d:/data/upload}")
    private String uploadPath;

    @Override
    public PageInfo<DocumentsInfo> getDocumentsList(DocumentsQuery documentsQuery) {

        Pageable pageable = PageableUtil.build(documentsQuery);
        PredicateBuilder<Documents> specCustom = Specifications.<Documents>and();
        specCustom.ne("delFlag",true);
        if (Objects.nonNull(documentsQuery.getDocType()))
            specCustom.eq("docType", documentsQuery.getDocType());


        try {
            com.linkyoyo.reportaudit.entity.SysOperator currentUser = SysUserUtils.currentUser();
//            RuleClass ruleClass = RuleClassUtils.getRuleClass(currentUser);
            if (currentUser != null && currentUser.getDeptId() != null) {
                specCustom.eq("deptId", currentUser.getDeptId());
//                log.info("当前用户规则分类ID: {}, 分类名称: {}", ruleClass.getId(), ruleClass.getClassName());
            }
        } catch (Exception e) {
            log.warn("获取用户规则分类失败: {}", e.getMessage());
        }


        com.linkyoyo.reportaudit.entity.SysOperator currentUser = SysUserUtils.currentUser();
        if (Objects.nonNull(currentUser)) {
            specCustom.eq("deptId", currentUser.getDeptId());
        }


        // 获取基础的Documents分页数据
        PageInfo<Documents> documentsPageInfo = PageableUtil.info(documentsRepository.findAll(
                Objects.isNull(documentsQuery.getWhere()) ? specCustom.build() :
                        specCustom.predicate(CommonFunc.<Documents>getWhere(documentsQuery)).build()
                , pageable));

        // 如果没有数据，直接返回空的PageInfo<DocumentsInfo>
        if (documentsPageInfo.getList().isEmpty()) {
            PageInfo<DocumentsInfo> emptyResult = new PageInfo<>();
            emptyResult.setList(java.util.Collections.emptyList());
            emptyResult.setTotal(0);
  /*          emptyResult.setPageNum(documentsPageInfo.getPageNum());
            emptyResult.setPageSize(documentsPageInfo.getPageSize());
            emptyResult.setPages(0);
            emptyResult.setSize(0);*/
            return emptyResult;
        }

        // 批量获取项目信息，提高性能（使用优化的查询方法）
        List<Integer> documentIds = documentsPageInfo.getList().stream()
                .map(Documents::getId)
                .collect(Collectors.toList());
        
        List<ProjectInfo> allProjectInfos = projectInfoRepository.findByDocumentIdIn(documentIds);
        
        // 创建documentId到ProjectInfo的映射
        Map<Integer, ProjectInfo> projectInfoMap = allProjectInfos.stream()
                .collect(Collectors.toMap(ProjectInfo::getDocumentId, p -> p, (existing, replacement) -> existing));

        // 转换为DocumentsInfo并填充项目信息
        List<DocumentsInfo> documentsInfoList = documentsPageInfo.getList().stream()
                .map(documents -> {
                    DocumentsInfo documentsInfo = new DocumentsInfo();
                    BeanUtils.copyProperties(documents, documentsInfo);
                    
                    // 清空mdContent字段，减少数据传输量，提升列表查询性能
                    documentsInfo.setMdContent(null);
                    
                    // 从映射中获取项目信息
                    ProjectInfo projectInfo = projectInfoMap.get(documents.getId());
                    if (projectInfo != null) {
                        documentsInfo.setProjectName(projectInfo.getProjectName());
                        documentsInfo.setReportType(projectInfo.getReportType());
                    }
                    
                    return documentsInfo;
                })
                .collect(Collectors.toList());

        // 创建新的PageInfo<DocumentsInfo>
        PageInfo<DocumentsInfo> result = new PageInfo<>();
        result.setList(documentsInfoList);
        result.setTotal(documentsPageInfo.getTotal());
        /*result.setPageNum(documentsPageInfo.getPageNum());
        result.setPageSize(documentsPageInfo.getPageSize());
        result.setPages(documentsPageInfo.getPages());
        result.setSize(documentsPageInfo.getSize());
        result.setStartRow(documentsPageInfo.getStartRow());
        result.setEndRow(documentsPageInfo.getEndRow());
        result.setHasNextPage(documentsPageInfo.isHasNextPage());
        result.setHasPreviousPage(documentsPageInfo.isHasPreviousPage());
        result.setIsFirstPage(documentsPageInfo.isIsFirstPage());
        result.setIsLastPage(documentsPageInfo.isIsLastPage());
        result.setNavigatePages(documentsPageInfo.getNavigatePages());
        result.setNavigatepageNums(documentsPageInfo.getNavigatepageNums());
        result.setNavigateFirstPage(documentsPageInfo.getNavigateFirstPage());
        result.setNavigateLastPage(documentsPageInfo.getNavigateLastPage());
        result.setFirstPage(documentsPageInfo.getFirstPage());
        result.setLastPage(documentsPageInfo.getLastPage());*/

        return result;
    }

    @Override
    public Documents createOrUpdate(DocumentsInfo documentsInfo) {
        if (Objects.isNull(documentsInfo.getId())) {
            Documents documents = Documents.builder().build();
            BeanUtils.copyProperties(documentsInfo, documents);
            documents = documentsRepository.save(documents);

            // 保存DocumentsToc明细数据
            if (Objects.nonNull(documentsInfo.getDocumentsTocList())) {
                // 先删除原有的DocumentsToc数据
                List<DocumentsToc> existingDocumentsTocList = documentsTocRepository.findAll(
                        Specifications.<DocumentsToc>and()
                                .eq("docId", documents.getId())
                                .build()
                );
                documentsTocRepository.deleteAll(existingDocumentsTocList);

                // 保存新的DocumentsToc数据
                List<DocumentsTocInfo> documentsTocList = documentsInfo.getDocumentsTocList();
                for (DocumentsTocInfo documentsTocInfo : documentsTocList) {
                    DocumentsToc documentsToc = DocumentsToc.builder().build();
                    BeanUtils.copyProperties(documentsTocInfo, documentsToc);
                    documentsToc.setDocId(documents.getId());
                    documentsTocRepository.save(documentsToc);
                }
            }
            return documents;
        } else {
            entityManager.clear();
            Documents documents = documentsRepository.findById(documentsInfo.getId()).orElse(null);
            if (documents != null) {
                BeanUtils.copyProperties(documentsInfo, documents);
                documents = documentsRepository.save(documents);

                // 保存DocumentsToc明细数据
                if (Objects.nonNull(documentsInfo.getDocumentsTocList())) {
                    // 先删除原有的DocumentsToc数据
                    List<DocumentsToc> existingDocumentsTocList = documentsTocRepository.findAll(
                            Specifications.<DocumentsToc>and()
                                    .eq("docId", documents.getId())
                                    .build()
                    );
                    documentsTocRepository.deleteAll(existingDocumentsTocList);

                    // 保存新的DocumentsToc数据
                    List<DocumentsTocInfo> documentsTocList = documentsInfo.getDocumentsTocList();
                    for (DocumentsTocInfo documentsTocInfo : documentsTocList) {
                        DocumentsToc documentsToc = DocumentsToc.builder().build();
                        BeanUtils.copyProperties(documentsTocInfo, documentsToc);
                        documentsToc.setDocId(documents.getId());
                        documentsTocRepository.save(documentsToc);
                    }
                }
            }
            return documents;
        }
    }

    @Override
    public DocumentsInfo getDocumentsDetail(Integer id) {
        entityManager.clear();
        Documents documents = documentsRepository.findById(id).orElse(null);
        DocumentsInfo documentsInfo = new DocumentsInfo();
        if (Objects.nonNull(documents))
            BeanUtils.copyProperties(documents, documentsInfo);

        // 查询DocumentsToc明细数据
        List<DocumentsToc> documentsTocList = documentsTocRepository.findAll(
                Specifications.<DocumentsToc>and()
                        .eq("docId", id)
                        .build()
        );

        // 转换为Info对象
        List<DocumentsTocInfo> documentsTocListInfo = documentsTocList.stream()
                .map(item -> {
                    DocumentsTocInfo info = new DocumentsTocInfo();
                    BeanUtils.copyProperties(item, info);
                    return info;
                })
                .collect(Collectors.toList());

        //增加 抽取结果list，检查结果list

        documentsInfo.setDocumentsTocList(documentsTocListInfo);

        // 查询关联的项目信息
        List<ProjectInfo> projectInfoList = projectInfoRepository.findAll(
                Specifications.<ProjectInfo>and()
                        .eq("documentId", id)
                        .build()
        );
        
        // 如果存在项目信息，取第一条并转换为Info对象
        if (!projectInfoList.isEmpty()) {
            ProjectInfo projectInfo = projectInfoList.get(0);
            ProjectInfoInfo projectInfoInfo = new ProjectInfoInfo();
            BeanUtils.copyProperties(projectInfo, projectInfoInfo);
            documentsInfo.setProjectInfo(projectInfoInfo);
        }

        // 查询关联的抽取结果并转换为Info对象
        List<DocumentsExtraction> documentsExtractionList = documentsExtractionRepository.findAll(
                Specifications.<DocumentsExtraction>and()
                        .eq("docId", id)
                        .build()
        );
        List<DocumentsExtractionInfo> documentsExtractionInfoList = documentsExtractionList.stream()
                .map(item -> {
                    DocumentsExtractionInfo info = new DocumentsExtractionInfo();
                    BeanUtils.copyProperties(item, info);
                    return info;
                })
                .sorted((a, b) -> {
                    if (a.getExtractionRuleId() == null && b.getExtractionRuleId() == null) return 0;
                    if (a.getExtractionRuleId() == null) return 1;
                    if (b.getExtractionRuleId() == null) return -1;
                    return a.getExtractionRuleId().compareTo(b.getExtractionRuleId());
                })
                .collect(Collectors.toList());
        documentsInfo.setDocumentsExtractioList(documentsExtractionInfoList);

// 查询关联的检查结果并转换为Info对象
        List<DocumentsCheckItems> documentsCheckItemsList = documentsCheckItemsRepository.findAll(
                Specifications.<DocumentsCheckItems>and()
                        .eq("docId", id)
                        .build()
        );
        List<DocumentsCheckItemsInfo> documentsCheckItemsInfoList = documentsCheckItemsList.stream()
                .map(item -> {
                    DocumentsCheckItemsInfo info = new DocumentsCheckItemsInfo();
                    BeanUtils.copyProperties(item, info);
                    return info;
                })
                .sorted((a, b) -> {
                    if (a.getCheckItemId() == null && b.getCheckItemId() == null) return 0;
                    if (a.getCheckItemId() == null) return 1;
                    if (b.getCheckItemId() == null) return -1;
                    return a.getCheckItemId().compareTo(b.getCheckItemId());
                })
                .collect(Collectors.toList());
        documentsInfo.setDocumentsCheckItemsList(documentsCheckItemsInfoList);

        return documentsInfo;
    }

    @Override
    public Documents uploadFileWithOcr(MultipartFile file, Integer docType) throws Exception {


        // 获取当前用户ID
        Long userId = Long.valueOf(SysUserUtils.currentUser().getId());

        // 计算文件MD5哈希值用于去重检查
        java.io.InputStream inputStream = file.getInputStream();
        String fileHash = org.apache.commons.codec.digest.DigestUtils.md5Hex(inputStream);
        inputStream.close();

        // 检查是否已存在相同MD5哈希的文件
        // 使用JPA Specification查询方法
        Documents existingDocument = documentsRepository.findAll(
                com.github.wenhao.jpa.Specifications.<Documents>and()
                        .eq("fileHash", fileHash)
                        .build()
        ).stream().findFirst().orElse(null);

        if (existingDocument != null) {
            // 如果文件已存在，直接返回已存在的文档对象
            return existingDocument;
        }

        // 生成UUID作为目录名
        String uuid = java.util.UUID.randomUUID().toString();

        // 从配置中获取上传路径
        // uploadPath is injected via @Value annotation

        // 创建UUID目录
        java.nio.file.Path uuidDir = java.nio.file.Paths.get(uploadPath, uuid);
        java.nio.file.Files.createDirectories(uuidDir);

        // 保存原始文件
        String originalFileName = file.getOriginalFilename();
        if (originalFileName == null) {
            originalFileName = "unnamed_file";
        }
        java.nio.file.Path originalFilePath = uuidDir.resolve(originalFileName);
        java.nio.file.Files.write(originalFilePath, file.getBytes());

        // 创建文档记录
        Documents document = new Documents();

        com.linkyoyo.reportaudit.entity.SysOperator currentUser = SysUserUtils.currentUser();
        if (Objects.nonNull(currentUser)) {
            document.setCreater(currentUser.getId());
            document.setDeptId(currentUser.getDeptId());
        }

        try {
            document.setFileName(uuid + "_" + originalFileName);
            document.setOriginalFileName(originalFileName);
            document.setFileType(getFileType(originalFileName));
            document.setFileSize(file.getSize());
            document.setFileHash(fileHash);
            document.setDirectory(uuid);
            document.setUploadUserId(userId);
            document.setProcessingStatus("OCR_PROCESSING");
            document.setDocType(docType != null ? docType : 0); // 设置文档类型，默认为0
            document.setDealFlag(0);
            document.setDelFlag(false);
            // 设置时间戳字段
            java.time.LocalDateTime now = java.time.LocalDateTime.now();
            document.setCreatedAt(now);
            document.setUpdatedAt(now);

            // 保存文档记录
            document = documentsRepository.save(document);
            
            // 异步处理OCR和后续操作，立即返回文档对象给前端
            java.io.File originalFile = originalFilePath.toFile();
            documentOcrProcessorService.processOcrAsync(originalFile, document.getId().intValue(), currentUser);

            return document;

        } catch (Exception e) {
            // 更新处理状态为OCR_FAILED
            if (document != null) {
                document.setProcessingStatus("OCR_FAILED");
                document.setProcessingError(e.getMessage());
                documentsRepository.save(document);
            }
            throw e;
        }
    }

    @Override
    @Transactional
    public Documents regenerateToc(Integer docId) throws Exception {
        // 1. 获取文档内容
        Documents document = documentsRepository.findById(docId)
                .orElseThrow(() -> new RuntimeException("未找到ID为 " + docId + " 的文档"));
                
        // 2. 检查是否有Markdown内容
        if (document.getMdContent() == null || document.getMdContent().trim().isEmpty()) {
            throw new RuntimeException("文档没有Markdown内容，无法生成目录");
        }
        
        try {
            // 3. 处理Markdown内容，生成目录
            Map<String, Object> result = ProcessRealFile.processMarkdownContent(document.getMdContent());
            
            // 4. 获取处理后的目录数据
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> tocList = (List<Map<String, Object>>) result.get("tableOfContents");
            
            if (tocList == null || tocList.isEmpty()) {
                throw new RuntimeException("未能从文档中提取出有效的目录结构");
            }
            
            // 5. 删除旧的目录数据
            documentsTocRepository.deleteByDocId(docId);
            
            // 6. 保存新的目录数据
            processTocData(docId, tocList);
            
            // 7. 更新文档的目录信息
//            document.setTocStatus(1); // 1 表示目录已生成
//            document.setUpdateTime(LocalDateTime.now());
            
            return documentsRepository.save(document);
        } catch (Exception e) {
            throw new RuntimeException("重新生成目录失败: " + e.getMessage(), e);
        }
    }

    @Override
    @Transactional
    public void markDeleted(Integer id) {
        Documents document = documentsRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("未找到ID为 " + id + " 的文档"));
        document.setDelFlag(Boolean.TRUE);
        document.setUpdatedAt(LocalDateTime.now());
        documentsRepository.save(document);
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
     */
    private void createExtractionTasks(Long docId) {
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

            // 获取当前用户信息
            com.linkyoyo.reportaudit.entity.SysOperator currentUser = SysUserUtils.currentUser();
            
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


    /**
     * 根据文件名获取文件类型
     *
     * @param fileName 文件名
     * @return 文件类型（PDF/DOCX/MD）
     */
    private String getFileType(String fileName) {
        if (fileName == null) {
            return "UNKNOWN";
        }
        String lowerFileName = fileName.toLowerCase();
        if (lowerFileName.endsWith(".pdf")) {
            return "PDF";
        } else if (lowerFileName.endsWith(".docx")) {
            return "DOCX";
        } else if (lowerFileName.endsWith(".md")) {
            return "MD";
        } else {
            return "UNKNOWN";
        }
    }
}
