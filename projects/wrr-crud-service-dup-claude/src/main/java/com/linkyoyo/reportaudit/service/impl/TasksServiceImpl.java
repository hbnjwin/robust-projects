package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.info.TasksInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.TasksQuery;
import com.linkyoyo.reportaudit.repository.TasksRepository;
import com.linkyoyo.reportaudit.service.TasksService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;
import com.linkyoyo.reportaudit.entity.CheckResult;
import com.linkyoyo.reportaudit.info.CheckResultInfo;
import com.linkyoyo.reportaudit.repository.CheckResultRepository;
import com.linkyoyo.reportaudit.entity.TasksCheckItems;
import com.linkyoyo.reportaudit.info.TasksCheckItemsInfo;
import com.linkyoyo.reportaudit.repository.TasksCheckItemsRepository;
import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.repository.DocumentsRepository;
import com.linkyoyo.reportaudit.info.ReferenceDocInfo;
import com.linkyoyo.reportaudit.entity.ProjectInfo;
import com.linkyoyo.reportaudit.repository.ProjectInfoRepository;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;
import com.github.wenhao.jpa.Specifications;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Service;

import java.util.Objects;
import java.util.UUID;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import java.util.ArrayList;
import java.util.Map;
import java.util.Set;
import java.util.HashSet;
import lombok.extern.slf4j.Slf4j;
import com.github.wenhao.jpa.PredicateBuilder;
import com.linkyoyo.reportaudit.util.SysUserUtils;
import com.linkyoyo.reportaudit.util.RuleClassUtils;
import com.linkyoyo.reportaudit.entity.RuleClass;
import com.linkyoyo.reportaudit.entity.CheckItems;
import com.linkyoyo.reportaudit.info.CheckItemsSimpleInfo;
import com.linkyoyo.reportaudit.repository.CheckItemsRepository;
import com.linkyoyo.reportaudit.util.wordreportgenerator.TaskReportGenerator;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.io.InputStream;

@Service
@Slf4j
public class TasksServiceImpl extends AbstractCrudServiceImpl<Tasks, TasksInfo, String>
        implements TasksService {

    @Autowired
    private TasksRepository tasksRepository;

    @Autowired
    private CheckResultRepository checkResultRepository;

    @Autowired
    private TasksCheckItemsRepository tasksCheckItemsRepository;

    @Autowired
    private DocumentsRepository documentsRepository;

    @Autowired
    private ProjectInfoRepository projectInfoRepository;

    @Autowired
    private CheckItemsRepository checkItemsRepository;

    // ---- AbstractCrudServiceImpl 抽象方法实现 ----

    @Override
    protected JpaRepository<Tasks, String> getRepository() {
        return tasksRepository;
    }

    @Override
    protected Tasks newEntity() {
        return Tasks.builder().build();
    }

    @Override
    protected String getInfoId(TasksInfo info) {
        return info.getId();
    }

    @Override
    protected void beforeCreate(Tasks entity, TasksInfo info) {
        com.linkyoyo.reportaudit.entity.SysOperator currentUser = SysUserUtils.currentUser();

        entity.setId(UUID.randomUUID().toString());
        entity.setCreatedAt(LocalDateTime.now());
        entity.setUpdatedAt(LocalDateTime.now());

        entity.setCreater(currentUser.getId());
        entity.setDeptId(currentUser.getDeptId());
        entity.setOperatorCode(currentUser.getOperatorCode());

        entity.setStatus("queued");
        entity.setDelFlag(false);

        populateFilenames(entity);

        if (Objects.isNull(entity.getTitle()))
            entity.setTitle("审查文档:" + entity.getOriginalFilename());
    }

    @Override
    protected void beforeUpdate(Tasks entity, TasksInfo info) {
        entity.setUpdatedAt(LocalDateTime.now());
        populateFilenames(entity);
    }

    @Override
    protected String[] getUpdateExcludeProperties() {
        return new String[]{"title", "status", "createdAt", "updatedAt", "startedAt",
                "completedAt", "result", "error", "creater", "deptId", "operatorCode", "progress"};
    }

    @Override
    protected List<ChildTableHandler<Tasks, TasksInfo, ?, ?>> getChildTableHandlers() {
        return Arrays.asList(
                ChildTableHandler.of(
                        checkResultRepository,
                        "taskId",
                        TasksInfo::getCheckResultList,
                        () -> CheckResult.builder().build(),
                        (child, parent) -> child.setTaskId(parent.getId()),
                        parent -> parent.getId()
                ),
                ChildTableHandler.of(
                        tasksCheckItemsRepository,
                        "taskId",
                        TasksInfo::getTasksCheckItemsList,
                        () -> TasksCheckItems.builder().build(),
                        (child, parent) -> child.setTaskId(parent.getId()),
                        parent -> parent.getId()
                )
        );
    }

    /** 根据文档 ID 填充原文件名和可研报告文件名 */
    private void populateFilenames(Tasks tasks) {
        if (Objects.nonNull(tasks.getOriginalDocId())) {
            try {
                Documents originalDoc = documentsRepository.findById(tasks.getOriginalDocId()).orElse(null);
                if (Objects.nonNull(originalDoc) && Objects.nonNull(originalDoc.getOriginalFileName())) {
                    tasks.setOriginalFilename(originalDoc.getOriginalFileName());
                }
            } catch (Exception e) {
                log.warn("查询原文件信息失败: originalDocId={}, error={}",
                        tasks.getOriginalDocId(), e.getMessage());
            }
        }

        if (Objects.nonNull(tasks.getFeasibilityStudyReport())) {
            try {
                Documents feasibilityDoc = documentsRepository.findById(tasks.getFeasibilityStudyReport()).orElse(null);
                if (Objects.nonNull(feasibilityDoc) && Objects.nonNull(feasibilityDoc.getOriginalFileName())) {
                    tasks.setReferenceFilename(feasibilityDoc.getOriginalFileName());
                }
            } catch (Exception e) {
                log.warn("查询可研报告信息失败: feasibilityStudyReport={}, error={}",
                        tasks.getFeasibilityStudyReport(), e.getMessage());
            }
        }
    }

    // ---- 业务方法 ----

    @Override
    public PageInfo<TasksInfo> getTasksList(TasksQuery tasksQuery) {
        Pageable pageable = PageableUtil.build(tasksQuery);
        PredicateBuilder<Tasks> specCustom = Specifications.<Tasks>and();
        specCustom.ne("delFlag",true);

        // 性能优化：注释掉未使用的 RuleClass 查询（每次请求耗时 300+ms）
        // 如果后续需要基于规则分类过滤任务，可以取消注释并添加实际的过滤逻辑
        // 根据当前用户获取规则分类，添加基于规则分类的查询条件
        try {
            com.linkyoyo.reportaudit.entity.SysOperator currentUser = SysUserUtils.currentUser();
//            RuleClass ruleClass = RuleClassUtils.getRuleClass(currentUser);
            if (currentUser != null && currentUser.getDeptId() != null) {
                // 添加 class_id 的查询条件，这里假设 Tasks 实体有 classId 字段
                // 如果没有这个字段，需要根据实际业务逻辑调整查询条件
                specCustom.eq("deptId", currentUser.getDeptId());
//                log.info("当前用户规则分类ID: {}, 分类名称: {}", ruleClass.getId(), ruleClass.getClassName());
            }
        } catch (Exception e) {
            log.warn("获取用户规则分类失败: {}", e.getMessage());
        }

        // 获取基础的Tasks分页数据
        PageInfo<Tasks> tasksPageInfo = PageableUtil.info(tasksRepository.findAll(
                Objects.isNull(tasksQuery.getWhere()) ? specCustom.build() :
                        specCustom.predicate(CommonFunc.<Tasks>getWhere(tasksQuery)).build()
                , pageable));

        // 如果没有数据，直接返回空的PageInfo<TasksInfo>
        if (tasksPageInfo.getList().isEmpty()) {
            PageInfo<TasksInfo> emptyResult = new PageInfo<>();
            emptyResult.setList(java.util.Collections.emptyList());
            emptyResult.setTotal(0);
            return emptyResult;
        }

        // 批量获取相关文档信息
        List<Integer> originalDocIds = tasksPageInfo.getList().stream()
                .map(Tasks::getOriginalDocId)
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        List<Integer> feasibilityStudyIds = tasksPageInfo.getList().stream()
                .map(Tasks::getFeasibilityStudyReport)
                .filter(Objects::nonNull)
                .collect(Collectors.toList());

        // 合并所有需要查询的文档ID
        Set<Integer> allDocIds = new HashSet<>();
        allDocIds.addAll(originalDocIds);
        allDocIds.addAll(feasibilityStudyIds);

        // 批量查询文档信息（使用优化的查询方法）
        Map<Integer, Documents> documentsMap = java.util.Collections.emptyMap();
        if (!allDocIds.isEmpty()) {
            List<Integer> docIdList = new ArrayList<>(allDocIds);
            List<Documents> allDocuments = documentsRepository.findByIdIn(docIdList);
            documentsMap = allDocuments.stream()
                    .collect(Collectors.toMap(Documents::getId, d -> d, (existing, replacement) -> existing));
        }

        // 批量获取项目信息（使用优化的查询方法）
        Map<Integer, ProjectInfo> projectInfoMap = java.util.Collections.emptyMap();
        if (!allDocIds.isEmpty()) {
            List<Integer> docIdList = new ArrayList<>(allDocIds);
            List<ProjectInfo> allProjectInfos = projectInfoRepository.findByDocumentIdIn(docIdList);
            projectInfoMap = allProjectInfos.stream()
                    .collect(Collectors.toMap(ProjectInfo::getDocumentId, p -> p, (existing, replacement) -> existing));
        }

        // 转换为TasksInfo并填充新字段
        final Map<Integer, Documents> finalDocumentsMap = documentsMap;
        final Map<Integer, ProjectInfo> finalProjectInfoMap = projectInfoMap;
        List<TasksInfo> tasksInfoList = tasksPageInfo.getList().stream()
                .map(tasks -> {
                    TasksInfo tasksInfo = new TasksInfo();
                    BeanUtils.copyProperties(tasks, tasksInfo);

                    // 填充待审报告就绪状态
                    if (tasks.getOriginalDocId() != null) {
                        Documents originalDoc = finalDocumentsMap.get(tasks.getOriginalDocId());
                        if (originalDoc != null) {
                            tasksInfo.setOriginalDocReady(
                                originalDoc.getDealFlag() != null && originalDoc.getDealFlag() == 1
                            );
                        } else {
                            tasksInfo.setOriginalDocReady(false);
                        }

                        // 从ProjectInfo获取项目信息（基于originalDocId）
                        ProjectInfo projectInfo = finalProjectInfoMap.get(tasks.getOriginalDocId());
                        if (projectInfo != null) {
                            tasksInfo.setProjectName(projectInfo.getProjectName());
                            tasksInfo.setReportType(projectInfo.getReportType());
                        }
                    } else {
                        tasksInfo.setOriginalDocReady(false);
                    }

                    // 填充可研报告就绪状态
                    if (tasks.getFeasibilityStudyReport() != null) {
                        Documents feasibilityDoc = finalDocumentsMap.get(tasks.getFeasibilityStudyReport());
                        if (feasibilityDoc != null) {
                            tasksInfo.setFeasibilityStudyReady(
                                feasibilityDoc.getDealFlag() != null && feasibilityDoc.getDealFlag() == 1
                            );
                        } else {
                            tasksInfo.setFeasibilityStudyReady(false);
                        }
                    } else {
                        tasksInfo.setFeasibilityStudyReady(false);
                    }

                    return tasksInfo;
                })
                .collect(Collectors.toList());

        // 创建新的PageInfo<TasksInfo>
        PageInfo<TasksInfo> result = new PageInfo<>();
        result.setList(tasksInfoList);
        result.setTotal(tasksPageInfo.getTotal());

        return result;
    }

    @Override
    public TasksInfo getTasksDetail(String id) {
        entityManager.clear();
        Tasks tasks = tasksRepository.findById(id).orElse(null);
        TasksInfo tasksInfo = new TasksInfo();
        if (Objects.nonNull(tasks))
           BeanUtils.copyProperties(tasks, tasksInfo);

        // 查询CheckResult明细数据
        List<CheckResult> checkResultList = checkResultRepository.findAll(
            Specifications.<CheckResult>and()
                .eq("taskId", id)
                .build()
        );

        // 转换为Info对象
        List<CheckResultInfo> checkResultListInfo = checkResultList.stream()
            .map(item -> {
                CheckResultInfo info = new CheckResultInfo();
                BeanUtils.copyProperties(item, info);
                return info;
            })
         .collect(Collectors.toList());

        tasksInfo.setCheckResultList(checkResultListInfo);
        // 查询TasksCheckItems明细数据
        List<TasksCheckItems> tasksCheckItemsList = tasksCheckItemsRepository.findAll(
            Specifications.<TasksCheckItems>and()
                .eq("taskId", id)
                .build()
        );

        // 转换为Info对象
        List<TasksCheckItemsInfo> tasksCheckItemsListInfo = tasksCheckItemsList.stream()
            .map(item -> {
                TasksCheckItemsInfo info = new TasksCheckItemsInfo();
                BeanUtils.copyProperties(item, info);
                return info;
            })
            .collect(Collectors.toList());
        // 处理引用文档列表 - 解析referenceDocId JSONB字段
        List<ReferenceDocInfo> listReferenceDoc = new ArrayList<>();
        if (Objects.nonNull(tasks) && Objects.nonNull(tasks.getReferenceDocId()) && !tasks.getReferenceDocId().trim().isEmpty()) {
            try {
                ObjectMapper objectMapper = new ObjectMapper();
                // 解析JSONB格式的referenceDocId，期望格式如：[22, 23] 或 ["22", "23"]
                List<Integer> docIds = objectMapper.readValue(tasks.getReferenceDocId(), new TypeReference<List<Integer>>() {});

                // 批量查询Documents表获取文档信息
                if (!docIds.isEmpty()) {
                    List<Documents> documents = documentsRepository.findAllById(docIds);
                    listReferenceDoc = documents.stream()
                        .map(doc -> ReferenceDocInfo.builder()
                            .id(doc.getId())
                            .name(doc.getOriginalFileName())
                            .build())
                        .collect(Collectors.toList());
                }
            } catch (Exception e) {
                log.warn("解析referenceDocId失败: taskId={}, referenceDocId={}, error={}",
                    id, tasks.getReferenceDocId(), e.getMessage());
            }
        }
        tasksInfo.setListReferenceDoc(listReferenceDoc);

        // 处理检查项列表 - 解析selectedItems JSONB字段
        List<CheckItemsSimpleInfo> lstCheckItems = new ArrayList<>();
        if (Objects.nonNull(tasks) && Objects.nonNull(tasks.getSelectedItems()) && !tasks.getSelectedItems().trim().isEmpty()) {
            try {
                ObjectMapper objectMapper = new ObjectMapper();
                // 解析JSONB格式的selectedItems，期望格式如：[1, 2, 3] 或 ["1", "2", "3"]
                List<Integer> checkItemIds = objectMapper.readValue(tasks.getSelectedItems(), new TypeReference<List<Integer>>() {});

                // 批量查询CheckItems表获取检查项信息
                if (!checkItemIds.isEmpty()) {
                    List<CheckItems> checkItems = checkItemsRepository.findAllById(checkItemIds);
                    lstCheckItems = checkItems.stream()
                        .map(item -> CheckItemsSimpleInfo.builder()
                            .id(item.getId())
                            .name(item.getName())
                            .description(item.getDescription())
                            .build())
                        .collect(Collectors.toList());
                }
            } catch (Exception e) {
                log.warn("解析selectedItems失败: taskId={}, selectedItems={}, error={}",
                    id, tasks.getSelectedItems(), e.getMessage());
            }
        }
        tasksInfo.setLstCheckItems(lstCheckItems);

        tasksInfo.setTasksCheckItemsList(tasksCheckItemsListInfo);
        return tasksInfo;
    }

    @Override
    public void markDeleted(String id) {
        Tasks tasks = tasksRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("未找到ID为 " + id + " 的任务"));
        tasks.setDelFlag(Boolean.TRUE);
        tasks.setUpdatedAt(LocalDateTime.now());
        tasksRepository.save(tasks);
    }

    @Override
    public String generateTaskReport(String taskId, String outputPath) throws Exception {
        log.info("开始生成任务报告，任务ID: {}", taskId);

        // 1. 获取任务详情
        TasksInfo tasksInfo = getTasksDetail(taskId);
        if (tasksInfo == null) {
            throw new IllegalArgumentException("任务不存在，任务ID: " + taskId);
        }

        // 2. 确定输出路径
        String finalOutputPath = outputPath;
        if (finalOutputPath == null || finalOutputPath.trim().isEmpty()) {
            // 使用默认路径：output/task_report_{taskId}_{timestamp}.docx
            String timestamp = java.time.LocalDateTime.now()
                .format(java.time.format.DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
            String fileName = tasksInfo.getOriginalFilename();
            if (fileName == null || fileName.trim().isEmpty()) {
                fileName = taskId != null ? taskId : "task_report";
            } else {
                fileName = fileName.replaceAll("[\\\\/:*?\"<>|]", "_");
                int dotIndex = fileName.lastIndexOf('.');
                if (dotIndex > 0) {
                    fileName = fileName.substring(0, dotIndex);
                }
            }
            finalOutputPath = "output/auditReport_" + fileName + "_" + timestamp + ".docx";
        }

        // 3. 确保输出目录存在
        java.io.File outputFile = new java.io.File(finalOutputPath);
        if (outputFile.getParentFile() != null && !outputFile.getParentFile().exists()) {
            outputFile.getParentFile().mkdirs();
            log.info("创建输出目录: {}", outputFile.getParentFile().getAbsolutePath());
        }

        // 4. 获取模板路径（从 JAR 包中复制到临时文件）
        String templatePath;
        try {
            // 从类路径加载模板资源
            InputStream templateStream = getClass().getClassLoader()
                .getResourceAsStream("templates/task_report_template.docx");

            if (templateStream == null) {
                throw new RuntimeException("找不到报告模板文件: templates/task_report_template.docx");
            }

            // 创建临时文件
            Path tempTemplate = Files.createTempFile("task_report_template_", ".docx");

            // 将模板复制到临时文件
            Files.copy(templateStream, tempTemplate, StandardCopyOption.REPLACE_EXISTING);
            templateStream.close();

            templatePath = tempTemplate.toString();
            log.info("使用模板路径（临时文件）: {}", templatePath);
        } catch (Exception e) {
            log.error("获取模板路径失败", e);
            throw new RuntimeException("找不到报告模板文件: templates/task_report_template.docx", e);
        }

        // 5. 生成报告
        TaskReportGenerator generator = new TaskReportGenerator();
        generator.generateTaskReport(tasksInfo, templatePath, finalOutputPath);

        log.info("任务报告生成成功，文件路径: {}", finalOutputPath);
        return finalOutputPath;
    }
}
