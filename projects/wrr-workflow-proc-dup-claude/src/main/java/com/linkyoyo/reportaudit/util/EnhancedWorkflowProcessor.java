package com.linkyoyo.reportaudit.util;

import com.fasterxml.jackson.databind.JsonNode;
import com.linkyoyo.reportaudit.entity.*;
import com.linkyoyo.reportaudit.service.WorkflowEventRecorderService;
import com.linkyoyo.reportaudit.util.RuleClassUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import static com.linkyoyo.reportaudit.entity.QExtractionRules.extractionRules;
import static com.linkyoyo.reportaudit.entity.QDocumentsExtraction.documentsExtraction;
import static com.linkyoyo.reportaudit.entity.QDocuments.documents;

import java.math.BigDecimal;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;

/**
 * 增强版工作流处理器
 * 在原有功能基础上增加实时事件记录和入库功能
 */
@Slf4j
@Component
public class EnhancedWorkflowProcessor {

    @Autowired
    private RestTemplate restTemplate;

    @Autowired
    private WorkflowEventRecorderService eventRecorderService;

    @Autowired
    private com.linkyoyo.reportaudit.service.WorkflowResultService workflowResultService;

    @Autowired
    private com.linkyoyo.reportaudit.repository.TasksCheckItemsRepository tasksCheckItemsRepository;

    @Autowired
    private com.linkyoyo.reportaudit.repository.CheckResultRepository checkResultRepository;

    @Autowired
    private com.linkyoyo.reportaudit.repository.TasksRepository tasksRepository;

    @Autowired
    private WorkflowQueryHelper queryHelper;

    @Autowired
    private WorkflowSSEHelper sseHelper;

    /**
     * 清空检查任务相关数据
     * @param taskId 检查任务ID
     */
    private void clearCheckTaskData(String taskId) {
        try {
            log.info("开始清空检查任务相关数据: taskId={}", taskId);

            // 清空 tasks_check_items 表中对应 taskId 的数据
            int deletedItems = tasksCheckItemsRepository.findByTaskId(taskId).size();
            tasksCheckItemsRepository.deleteAll(tasksCheckItemsRepository.findByTaskId(taskId));
            log.info("已清空 tasks_check_items 数据: taskId={}, 删除记录数={}", taskId, deletedItems);

            // 清空 check_result 表中对应 taskId 的数据
            int deletedResults = checkResultRepository.findByTaskIdOrderByCreatedAtDesc(taskId).size();
            checkResultRepository.deleteAll(checkResultRepository.findByTaskIdOrderByCreatedAtDesc(taskId));
            log.info("已清空 check_result 数据: taskId={}, 删除记录数={}", taskId, deletedResults);

            log.info("检查任务相关数据清空完成: taskId={}, 总删除记录数={}", taskId, deletedItems + deletedResults);
        } catch (Exception e) {
            log.error("清空检查任务相关数据失败: taskId={}, error={}", taskId, e.getMessage(), e);
            throw new RuntimeException("清空检查任务相关数据失败: " + e.getMessage(), e);
        }
    }

    /**
     * 处理抽取任务（增强版 - 支持实时入库）
     * @param extractionTask 抽取任务实体
     * @param filesText 文档内容
     * @param eventHandler 事件处理器
     * @return 异步处理结果
     */
    public CompletableFuture<WorkflowResult> processExtractionTask(
            ExtractionTasks extractionTask,
            String filesText,
            Consumer<WorkflowEvent> eventHandler) {

        return CompletableFuture.supplyAsync(() -> {
            try {
                log.info("开始处理抽取任务（增强版）: {}", extractionTask.getId());

                List<Integer> selectedItems = queryHelper.parseSelectedItems(extractionTask.getSelectedItems());
                List<ExtractionRules> rules = queryHelper.getExtractionRules(selectedItems);
                WorkflowConfig config = getWorkflowConfig(extractionTask.getId(),"extraction");

                WorkflowResult result = new WorkflowResult();
                result.setTaskId(extractionTask.getId());
                result.setTaskType("extraction");
                result.setResults(new ArrayList<>());

                for (ExtractionRules rule : rules) {
                    try {
                        WorkflowItemResult itemResult = executeExtractionWorkflowWithRecording(
                            extractionTask, rule, filesText, config, eventHandler);
                        result.getResults().add(itemResult);
                    } catch (Exception e) {
                        log.error("处理抽取项失败: ruleId={}, error={}", rule.getId(), e.getMessage(), e);
                        WorkflowItemResult errorResult = new WorkflowItemResult();
                        errorResult.setItemId(rule.getId());
                        errorResult.setItemName(rule.getRuleName());
                        errorResult.setSuccess(false);
                        errorResult.setError(e.getMessage());
                        result.getResults().add(errorResult);
                    }
                }

                log.info("抽取任务处理完成（增强版）: {}", extractionTask.getId());
                return result;

            } catch (Exception e) {
                log.error("处理抽取任务失败（增强版）: {}", e.getMessage(), e);
                WorkflowResult errorResult = new WorkflowResult();
                errorResult.setTaskId(extractionTask.getId());
                errorResult.setTaskType("extraction");
                errorResult.setSuccess(false);
                errorResult.setError(e.getMessage());
                return errorResult;
            }
        });
    }

    /**
     * 处理检查任务（增强版 - 支持实时入库）
     * @param task 检查任务实体
     * @param filesText 文档内容
     * @param eventHandler 事件处理器
     * @return 异步处理结果
     */
    public CompletableFuture<WorkflowResult> processCheckTask(
            Tasks task,
            String filesText,
            Consumer<WorkflowEvent> eventHandler) {

        return CompletableFuture.supplyAsync(() -> {
            try {
                log.info("开始处理检查任务（增强版）: {}", task.getId());

                List<Integer> selectedItems = queryHelper.parseSelectedItems(task.getSelectedItems());
                List<CheckItems> checkItemsList = queryHelper.getCheckItems(selectedItems);
                WorkflowConfig config = getWorkflowConfig(task.getId(),"check");

                WorkflowResult result = new WorkflowResult();
                result.setTaskId(task.getId());
                result.setTaskType("check");
                result.setResults(new ArrayList<>());

                for (CheckItems checkItem : checkItemsList) {
                    try {
                        WorkflowItemResult itemResult = executeCheckWorkflowWithRecording(
                            task, checkItem, filesText, config, eventHandler);
                        result.getResults().add(itemResult);
                    } catch (Exception e) {
                        log.error("处理检查项失败: checkId={}, error={}", checkItem.getId(), e.getMessage(), e);
                        WorkflowItemResult errorResult = new WorkflowItemResult();
                        errorResult.setItemId(checkItem.getId());
                        errorResult.setItemName(checkItem.getName());
                        errorResult.setSuccess(false);
                        errorResult.setError(e.getMessage());
                        result.getResults().add(errorResult);
                    }
                }

                log.info("检查任务处理完成（增强版）: {}", task.getId());
                return result;

            } catch (Exception e) {
                log.error("处理检查任务失败（增强版）: {}", e.getMessage(), e);
                WorkflowResult errorResult = new WorkflowResult();
                errorResult.setTaskId(task.getId());
                errorResult.setTaskType("check");
                errorResult.setSuccess(false);
                errorResult.setError(e.getMessage());
                return errorResult;
            }
        });
    }

    /**
     * 执行抽取工作流（增强版 - 支持实时入库）
     */
    private WorkflowItemResult executeExtractionWorkflowWithRecording(
            ExtractionTasks task,
            ExtractionRules rule,
            String filesText,
            WorkflowConfig config,
            Consumer<WorkflowEvent> eventHandler) throws Exception {

        // 执行工作流前的config处理：如果 rule.agentPara 不为空，则设置为配置项里面的参数配置
        WorkflowConfig finalConfig = config;
        if (rule.getAgentPara() != null && !rule.getAgentPara().trim().isEmpty()) {
            try {
                log.info("检测到 rule.agentPara 配置，将覆盖默认配置: ruleId={}, ruleName={}",
                    rule.getId(), rule.getRuleName());

                WorkflowConfig ruleConfig = queryHelper.getObjectMapper().readValue(rule.getAgentPara(), WorkflowConfig.class);
                finalConfig = ruleConfig;

                log.info("成功应用 rule.agentPara 配置: ruleId={}, extractionUrl={}",
                    rule.getId(),
                    ruleConfig.getExtractionTemplate() != null ? ruleConfig.getExtractionTemplate().getUrl() : "null");

            } catch (Exception e) {
                log.warn("解析 rule.agentPara 配置失败，使用默认配置: ruleId={}, error={}",
                    rule.getId(), e.getMessage());
            }
        } else {
            log.debug("rule.agentPara 为空，使用默认配置: ruleId={}", rule.getId());
        }

        // 构建请求体
        Map<String, Object> requestBody = sseHelper.buildExtractionRequestBody(task, rule, filesText, finalConfig);

        // 创建增强的事件处理器（包含入库功能）
        Consumer<WorkflowEvent> enhancedEventHandler = createEnhancedExtractionEventHandler(
            eventHandler, task.getId(), rule.getId(), rule.getRuleName(),
            String.valueOf(task.getOriginalDocId()));

        // 执行工作流调用
        return executeWorkflowCall(
            finalConfig.getExtractionTemplate().getUrl(),
            finalConfig.getExtractionTemplate().getToken(),
            requestBody,
            rule.getId(),
            rule.getRuleName(),
            enhancedEventHandler
        );
    }

    /**
     * 执行检查工作流（增强版 - 支持实时入库）
     */
    private WorkflowItemResult executeCheckWorkflowWithRecording(
            Tasks task,
            CheckItems checkItem,
            String filesText,
            WorkflowConfig config,
            Consumer<WorkflowEvent> eventHandler) throws Exception {

        // 执行工作流前的config处理：如果 checkItem.agentPara 不为空，则设置为配置项里面的参数配置
        WorkflowConfig finalConfig = config;
        if (checkItem.getAgentPara() != null && !checkItem.getAgentPara().trim().isEmpty()) {
            try {
                log.info("检测到 checkItem.agentPara 配置，将覆盖默认配置: checkItemId={}, checkItemName={}",
                    checkItem.getId(), checkItem.getName());

                WorkflowConfig checkItemConfig = queryHelper.getObjectMapper().readValue(checkItem.getAgentPara(), WorkflowConfig.class);
                finalConfig = checkItemConfig;

                log.info("成功应用 checkItem.agentPara 配置: checkItemId={}, checkUrl={}",
                    checkItem.getId(),
                    checkItemConfig.getCheckTemplate() != null ? checkItemConfig.getCheckTemplate().getUrl() : "null");

            } catch (Exception e) {
                log.warn("解析 checkItem.agentPara 配置失败，使用默认配置: checkItemId={}, error={}",
                    checkItem.getId(), e.getMessage());
            }
        } else {
            log.debug("checkItem.agentPara 为空，使用默认配置: checkItemId={}", checkItem.getId());
        }

        // 构建请求体
        Map<String, Object> requestBody = buildCheckRequestBody(task, checkItem, filesText, finalConfig);

        // 创建增强的事件处理器（包含入库功能）
        Consumer<WorkflowEvent> enhancedEventHandler = createEnhancedCheckEventHandler(
            eventHandler, task.getId(), checkItem.getId(), checkItem.getName(),
            task.getOriginalPath());

        // 执行工作流调用
        return executeWorkflowCall(
            finalConfig.getCheckTemplate().getUrl(),
            finalConfig.getCheckTemplate().getToken(),
            requestBody,
            checkItem.getId(),
            checkItem.getName(),
            enhancedEventHandler
        );
    }

    /**
     * 创建增强的抽取任务事件处理器
     */
    private Consumer<WorkflowEvent> createEnhancedExtractionEventHandler(
            Consumer<WorkflowEvent> originalHandler,
            String extractionTaskId,
            Integer extractionRuleId,
            String extractionRuleName,
            String documentId) {

        return event -> {
            try {
                if (originalHandler != null) {
                    originalHandler.accept(event);
                }
                eventRecorderService.handleExtractionWorkflowEvent(
                    event, extractionTaskId, extractionRuleId, extractionRuleName, documentId);
            } catch (Exception e) {
                log.error("增强事件处理器执行失败: extractionTaskId={}, ruleId={}, error={}",
                    extractionTaskId, extractionRuleId, e.getMessage(), e);
            }
        };
    }

    /**
     * 创建增强的检查任务事件处理器
     */
    private Consumer<WorkflowEvent> createEnhancedCheckEventHandler(
            Consumer<WorkflowEvent> originalHandler,
            String taskId,
            Integer checkItemId,
            String checkItemName,
            String documentId) {

        return event -> {
            try {
                if (originalHandler != null) {
                    originalHandler.accept(event);
                }
                eventRecorderService.handleCheckWorkflowEvent(
                    event, taskId, checkItemId, checkItemName, documentId);
            } catch (Exception e) {
                log.error("增强事件处理器执行失败: taskId={}, checkItemId={}, error={}",
                    taskId, checkItemId, e.getMessage(), e);
            }
        };
    }

    /**
     * 执行工作流API调用（流式输出处理）
     */
    private WorkflowItemResult executeWorkflowCall(
            String url,
            String token,
            Map<String, Object> requestBody,
            Integer itemId,
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws Exception {

        log.info("调用工作流API（流式输出）: url={}, itemId={}, itemName={}", url, itemId, itemName);

        return restTemplate.execute(url, HttpMethod.POST,
            clientHttpRequest -> {
                clientHttpRequest.getHeaders().setContentType(MediaType.APPLICATION_JSON);
                clientHttpRequest.getHeaders().setBearerAuth(token);
                try {
                    String requestBodyJson = queryHelper.getObjectMapper().writeValueAsString(requestBody);
                    clientHttpRequest.getBody().write(requestBodyJson.getBytes("UTF-8"));
                } catch (Exception e) {
                    log.error("写入请求体失败: {}", e.getMessage(), e);
                    throw new RuntimeException("写入请求体失败", e);
                }
            },
            clientHttpResponse -> {
                HttpStatus statusCode = clientHttpResponse.getStatusCode();
                if (statusCode == HttpStatus.OK) {
                    log.info("开始处理流式响应: itemId={}, itemName={}", itemId, itemName);
                    return sseHelper.processStreamResponse(
                        clientHttpResponse.getBody(), itemId, itemName, eventHandler);
                } else {
                    String errorMessage = String.format("工作流调用失败: %s", statusCode);
                    log.error(errorMessage);
                    throw new RuntimeException(errorMessage);
                }
            }
        );
    }

    /**
     * 构建检查任务请求体（Enhanced特有字段映射）
     */
    private Map<String, Object> buildCheckRequestBody(
            Tasks task,
            CheckItems checkItem,
            String filesText,
            WorkflowConfig config) {

        Map<String, Object> inputs = new HashMap<>();
        inputs.put("taskId", task.getId());
        inputs.put("documentId", String.valueOf(task.getOriginalDocId()));
        inputs.put("files_text", filesText);
        inputs.put("extractRules", checkItem.getPrompt());
        inputs.put("extractionId", String.valueOf(checkItem.getId()));
        inputs.put("checkBranch_1", "是");
        inputs.put("extractionName", checkItem.getName());

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("files", new ArrayList<>());
        requestBody.put("inputs", inputs);
        requestBody.put("response_mode", "streaming");

        try {
            String requestBodyJson = queryHelper.getObjectMapper().writeValueAsString(requestBody);
            log.info("检查任务请求体（增强版）: {}", requestBodyJson);
        } catch (Exception e) {
            log.warn("输出请求体日志失败: {}", e.getMessage());
        }

        return requestBody;
    }

    /**
     * 增强版检查任务处理（同步执行）- 支持关联抽取内容
     * @param task 检查任务实体
     * @param eventHandler 事件处理器
     * @return 同步处理结果
     */
    public WorkflowResult executeEnhanceCheckTaskSync(
            Tasks task,
            Consumer<WorkflowEvent> eventHandler) {
        return executeEnhanceCheckTaskSync(task, eventHandler, true);
    }

    public WorkflowResult executeEnhanceCheckTaskSync(
            Tasks task,
            Consumer<WorkflowEvent> eventHandler,
            boolean shouldClearData) {

        try {
            log.info("开始处理增强版检查任务（同步）: {}", task.getId());

            if (shouldClearData) {
                clearCheckTaskData(task.getId());
            } else {
                log.info("跳过数据清空，保留现有进度: taskId={}", task.getId());
            }

            List<Integer> selectedItems = queryHelper.parseSelectedItems(task.getSelectedItems());
            List<CheckItems> checkItemsList = queryHelper.getCheckItems(selectedItems);
            WorkflowConfig config = getWorkflowConfig(task.getId(),"check");

            WorkflowResult result = new WorkflowResult();
            result.setTaskId(task.getId());
            result.setTaskType("enhance_check");
            result.setResults(new ArrayList<>());

            for (CheckItems checkItem : checkItemsList) {
                try {
                    String enhancedFilesText = buildEnhancedFilesText(task, checkItem);

                    WorkflowItemResult itemResult = executeCheckWorkflowWithRecording(
                        task, checkItem, enhancedFilesText, config, eventHandler);
                    result.getResults().add(itemResult);
                } catch (Exception e) {
                    log.error("处理增强版检查项失败: checkId={}, error={}", checkItem.getId(), e.getMessage(), e);
                    WorkflowItemResult errorResult = new WorkflowItemResult();
                    errorResult.setItemId(checkItem.getId());
                    errorResult.setItemName(checkItem.getName());
                    errorResult.setSuccess(false);
                    errorResult.setError(e.getMessage());
                    result.getResults().add(errorResult);
                }
            }

            log.info("增强版检查任务处理完成（同步）: {}", task.getId());

            try {
                log.info("增强版工作流执行完成，开始处理结果入库: taskId={}", task.getId());
                java.util.Map<String, Object> processResult = workflowResultService.processWorkflowResult(result, "");

                if ((Boolean) processResult.get("success")) {
                    log.info("增强版工作流结果处理成功: taskId={}, message={}",
                        task.getId(), processResult.get("message"));
                } else {
                    log.warn("增强版工作流结果处理失败: taskId={}, message={}",
                        task.getId(), processResult.get("message"));
                }

                result.setProcessResult(processResult);

            } catch (Exception e) {
                log.error("处理增强版工作流结果异常: taskId={}, error={}", task.getId(), e.getMessage(), e);
            }

            return result;

        } catch (Exception e) {
            log.error("处理增强版检查任务失败（同步）: {}", e.getMessage(), e);
            WorkflowResult errorResult = new WorkflowResult();
            errorResult.setTaskId(task.getId());
            errorResult.setTaskType("enhance_check");
            errorResult.setSuccess(false);
            errorResult.setError(e.getMessage());
            return errorResult;
        }
    }

    /**
     * 构建增强版的文件内容
     * 根据检查项的关联配置动态获取内容
     */
    private String buildEnhancedFilesText(Tasks task, CheckItems checkItem) throws Exception {
        List<Map<String, Object>> documentContents = new ArrayList<>();

        if (Boolean.TRUE.equals(checkItem.getRelationExtraction())) {
            List<Map<String, Object>> originalDocContents = getExtractionContentsByDocId(
                task.getOriginalDocId(), checkItem.getId());
            documentContents.addAll(originalDocContents);
        } else {
            Map<String, Object> originalDocContent = getOriginalDocumentContent(task.getOriginalDocId());
            if (originalDocContent != null) {
                documentContents.add(originalDocContent);
            }
        }

        if (Boolean.TRUE.equals(checkItem.getRelationReference()) && task.getReferenceDocId() != null) {
            List<Integer> referenceDocIds = parseReferenceDocIds(task.getReferenceDocId());
            for (Integer refDocId : referenceDocIds) {
                List<Map<String, Object>> refDocContents = getExtractionContentsByDocId(
                    refDocId, checkItem.getId());
                documentContents.addAll(refDocContents);
            }
        }

        if (Boolean.TRUE.equals(checkItem.getRelationStudy()) && task.getFeasibilityStudyReport() != null) {
            List<Map<String, Object>> studyDocContents = getExtractionContentsByDocId(
                task.getFeasibilityStudyReport(), checkItem.getId());
            documentContents.addAll(studyDocContents);
        }

        try {
            String result = queryHelper.getObjectMapper().writeValueAsString(documentContents);
            log.info("构建的增强版文件内容: checkItemId={}, contentSize={}",
                checkItem.getId(), documentContents.size());
            return result;
        } catch (Exception e) {
            log.error("序列化文档内容失败: {}", e.getMessage(), e);
            throw new RuntimeException("构建增强版文件内容失败", e);
        }
    }

    /**
     * 根据文档ID和检查项ID获取抽取内容
     */
    private List<Map<String, Object>> getExtractionContentsByDocId(Integer docId, Integer checkItemId) {
        List<Map<String, Object>> contents = new ArrayList<>();

        try {
            List<DocumentsExtraction> extractions = queryHelper.getQueryFactory()
                .selectFrom(documentsExtraction)
                .leftJoin(extractionRules).on(documentsExtraction.extractionRuleId.eq(extractionRules.id))
                .where(documentsExtraction.docId.eq(docId)
                    .and(extractionRules.refCheckItemId.eq(checkItemId))
                    .and(documentsExtraction.extractedContent.isNotNull()))
                .fetch();

            Documents document = queryHelper.getQueryFactory()
                .selectFrom(documents)
                .where(documents.id.eq(docId))
                .fetchOne();

            String docName = document != null ? document.getOriginalFileName() : "未知文档";

            StringBuilder extractionContent = new StringBuilder();
            for (DocumentsExtraction extraction : extractions) {
                if (extraction.getExtractedContent() != null && !extraction.getExtractedContent().trim().isEmpty()) {
                    if (extractionContent.length() > 0) {
                        extractionContent.append("\n\n");
                    }
                    extractionContent.append("【").append(extraction.getExtractionRuleName()).append("】\n");
                    extractionContent.append(extraction.getExtractedContent());
                }
            }

            if (extractionContent.length() > 0) {
                Map<String, Object> content = new HashMap<>();
                content.put("docId", docId);
                content.put("docName", docName);
                content.put("extractionContent", extractionContent.toString());
                contents.add(content);
            }

        } catch (Exception e) {
            log.error("获取抽取内容失败: docId={}, checkItemId={}, error={}",
                docId, checkItemId, e.getMessage(), e);
        }

        return contents;
    }

    /**
     * 获取原始文档内容（非抽取内容）
     */
    private Map<String, Object> getOriginalDocumentContent(Integer docId) {
        try {
            Documents document = queryHelper.getQueryFactory()
                .selectFrom(documents)
                .where(documents.id.eq(docId))
                .fetchOne();

            if (document != null && document.getMdContent() != null && !document.getMdContent().trim().isEmpty()) {
                Map<String, Object> content = new HashMap<>();
                content.put("docId", docId);
                content.put("docName", document.getOriginalFileName());
                content.put("extractionContent", document.getMdContent());
                return content;
            }
        } catch (Exception e) {
            log.error("获取原始文档内容失败: docId={}, error={}", docId, e.getMessage(), e);
        }

        return null;
    }

    /**
     * 解析参考文档ID列表
     */
    private List<Integer> parseReferenceDocIds(String referenceDocIdJson) {
        if (referenceDocIdJson == null || referenceDocIdJson.trim().isEmpty()) {
            return new ArrayList<>();
        }

        try {
            JsonNode node = queryHelper.getObjectMapper().readTree(referenceDocIdJson);
            List<Integer> docIds = new ArrayList<>();
            if (node.isArray()) {
                for (JsonNode item : node) {
                    docIds.add(item.asInt());
                }
            }
            return docIds;
        } catch (Exception e) {
            log.error("解析参考文档ID失败: {}", e.getMessage());
            return new ArrayList<>();
        }
    }

    /**
     * 获取工作流配置（保持向后兼容）
     */
    private WorkflowConfig getWorkflowConfig(String taskId) {
        return getWorkflowConfig(taskId, null);
    }

    /**
     * 获取工作流配置（支持任务类型区分）
     * 优先级：
     * 1. 先根据任务创建者获取对应的规则分类，从规则分类的 agent_para 获取配置
     * 2. 如果获取失败，则从 sysParaset 表获取默认配置
     */
    private WorkflowConfig getWorkflowConfig(String taskId, String taskType) {
        try {
            String configJson = getConfigFromRuleClass(taskId, taskType);

            if (configJson == null || configJson.trim().isEmpty()) {
                log.info("规则分类配置为空，使用默认配置: taskId={}, taskType={}", taskId, taskType);
                return queryHelper.getDefaultWorkflowConfig();
            }

            return queryHelper.getObjectMapper().readValue(configJson, WorkflowConfig.class);
        } catch (Exception e) {
            log.error("获取工作流配置失败: taskId={}, taskType={}, error={}", taskId, taskType, e.getMessage());
            throw new RuntimeException("无法获取工作流配置", e);
        }
    }

    /**
     * 从规则分类获取 agent_para 配置（保持向后兼容）
     */
    private String getConfigFromRuleClass(String taskId) {
        return getConfigFromRuleClass(taskId, null);
    }

    /**
     * 从规则分类获取 agent_para 配置（支持任务类型区分）
     */
    private String getConfigFromRuleClass(String taskId, String taskType) {
        try {
            Integer creater = null;

            if ("extraction".equals(taskType)) {
                ExtractionTasks extractionTask = queryHelper.getQueryFactory()
                    .selectFrom(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks)
                    .where(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks.id.eq(taskId))
                    .fetchOne();

                if (extractionTask != null) {
                    creater = extractionTask.getCreater();
                    log.debug("从 extraction_tasks 表获取创建者: taskId={}, creater={}", taskId, creater);
                }
            } else if ("check".equals(taskType)) {
                Tasks task = queryHelper.getQueryFactory()
                    .selectFrom(com.linkyoyo.reportaudit.entity.QTasks.tasks)
                    .where(com.linkyoyo.reportaudit.entity.QTasks.tasks.id.eq(taskId))
                    .fetchOne();

                if (task != null) {
                    creater = task.getCreater();
                    log.debug("从 tasks 表获取创建者: taskId={}, creater={}", taskId, creater);
                }
            } else {
                ExtractionTasks extractionTask = queryHelper.getQueryFactory()
                    .selectFrom(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks)
                    .where(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks.id.eq(taskId))
                    .fetchOne();

                if (extractionTask != null) {
                    creater = extractionTask.getCreater();
                    log.debug("自动检测为 extraction 任务: taskId={}, creater={}", taskId, creater);
                } else {
                    Tasks task = queryHelper.getQueryFactory()
                        .selectFrom(com.linkyoyo.reportaudit.entity.QTasks.tasks)
                        .where(com.linkyoyo.reportaudit.entity.QTasks.tasks.id.eq(taskId))
                        .fetchOne();

                    if (task != null) {
                        creater = task.getCreater();
                        log.debug("自动检测为 check 任务: taskId={}, creater={}", taskId, creater);
                    }
                }
            }

            if (creater == null) {
                log.warn("未找到任务或任务创建者信息: taskId={}", taskId);
                return null;
            }

            SysOperator sysOperator = queryHelper.getQueryFactory()
                .selectFrom(com.linkyoyo.reportaudit.entity.QSysOperator.sysOperator)
                .where(QSysOperator.sysOperator.id.eq(creater))
                .fetchOne();

            if (sysOperator == null) {
                log.warn("未找到创建者信息: creater={}", creater);
                return null;
            }

            RuleClass ruleClass = RuleClassUtils.getRuleClass(sysOperator);
            if (ruleClass != null && ruleClass.getAgentPara() != null) {
                log.info("从规则分类获取配置: taskId={}, ruleClassId={}, className={}",
                    taskId, ruleClass.getId(), ruleClass.getClassName());
                return ruleClass.getAgentPara();
            }

            return null;
        } catch (Exception e) {
            log.warn("从规则分类获取配置失败: taskId={}, taskType={}, error={}", taskId, taskType, e.getMessage());
            return null;
        }
    }

    /**
     * 从sysParaset表获取工作流配置（保持向后兼容）
     */
    private WorkflowConfig getWorkflowConfig() {
        return getWorkflowConfig(null);
    }

    /**
     * 异步执行增强版检查任务
     * 使用@Async注解确保事务上下文正确传播
     */
    @Async
    public void executeEnhanceCheckTaskAsync(Tasks task, String taskId,
            com.linkyoyo.reportaudit.service.TaskProgressNotificationService taskProgressNotificationService) {
        try {
            task.setStatus("started");
            task.setStartedAt(java.time.LocalDateTime.now());
            task.setProgress(BigDecimal.valueOf(0.00));
            task.setUpdatedAt(java.time.LocalDateTime.now());
            task = tasksRepository.save(task);

            log.info("任务状态已强制设置为执行中: taskId={}", taskId);

            clearCheckTaskData(taskId);
            log.info("已清空任务相关数据，准备重新执行: taskId={}", taskId);

            taskProgressNotificationService.notifyTaskProgress(taskId, "check", "工作流开始执行", "");

            Consumer<WorkflowEvent> eventHandler = event -> {
                String eventInfo = String.format("[%s] %s - %s",
                    event.getEvent(), event.getWorkflowRunId(), event.getData());
                log.info("增强版工作流事件: {}", eventInfo);

                if (event.getEvent().equals("workflow_finished") || event.getEvent().equals("workflow_failed")) {
                    String statusMessage = event.getEvent().equals("workflow_finished") ? "工作流执行完成" : "工作流执行失败";
                    taskProgressNotificationService.notifyTaskProgress(taskId, "check", statusMessage, "");
                }
            };

            WorkflowResult result = executeEnhanceCheckTaskSync(task, eventHandler, false);

            if (result.isSuccess()) {
                log.info("增强版工作流任务执行成功: taskId={}, itemCount={}",
                    taskId, result.getItemResults() != null ? result.getItemResults().size() : 0);

                task.setStatus("completed");
                task.setCompletedAt(java.time.LocalDateTime.now());
                task.setUpdatedAt(java.time.LocalDateTime.now());
                tasksRepository.save(task);

                taskProgressNotificationService.notifyTaskCompleted(taskId, "check", true);
            } else {
                log.error("增强版工作流任务执行失败: taskId={}, error={}", taskId, result.getErrorMessage());

                task.setStatus("failed");
                task.setUpdatedAt(java.time.LocalDateTime.now());
                task.setErrorMessage(result.getErrorMessage());
                tasksRepository.save(task);

                taskProgressNotificationService.notifyTaskError(taskId, "check", result.getErrorMessage());
            }

        } catch (Exception e) {
            log.error("异步执行增强版工作流任务异常: taskId={}, error={}", taskId, e.getMessage(), e);
            taskProgressNotificationService.notifyTaskError(taskId, "check", "执行异常: " + e.getMessage());
        }
    }

    /**
     * 更新任务状态
     */
    private void updateTaskStatus(String taskId, String status, String errorMessage) {
        updateTaskStatus(taskId, status, null, errorMessage);
    }

    /**
     * 更新任务状态和进度
     */
    private void updateTaskStatus(String taskId, String status, BigDecimal progress, String errorMessage) {
        try {
            log.info("开始更新任务状态: taskId={}, status={}", taskId, status);

            Optional<com.linkyoyo.reportaudit.entity.Tasks> taskOpt = tasksRepository.findById(taskId);
            if (taskOpt.isPresent()) {
                com.linkyoyo.reportaudit.entity.Tasks task = taskOpt.get();
                log.info("找到任务，当前状态: taskId={}, currentStatus={}", taskId, task.getStatus());

                task.setStatus(status);

                if (progress != null) {
                    task.setProgress(progress);
                }

                task.setUpdatedAt(java.time.LocalDateTime.now());
                if (errorMessage != null) {
                    task.setErrorMessage(errorMessage);
                }

                com.linkyoyo.reportaudit.entity.Tasks savedTask = tasksRepository.save(task);
                log.info("任务状态保存完成: taskId={}, newStatus={}, savedStatus={}",
                    taskId, status, savedTask.getStatus());

                String progressInfo = progress != null ? String.format(", progress=%.2f%%", progress) : "";
                log.info("任务状态已更新: taskId={}, status={}{}", taskId, status, progressInfo);
            } else {
                log.warn("未找到任务，无法更新状态: taskId={}", taskId);
            }
        } catch (Exception e) {
            log.error("更新任务状态失败: taskId={}, status={}, error={}", taskId, status, e.getMessage(), e);
        }
    }
}
