package com.linkyoyo.reportaudit.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.*;
import com.linkyoyo.reportaudit.service.WorkflowEventRecorderService;
import com.linkyoyo.reportaudit.util.RuleClassUtils;
import com.linkyoyo.reportaudit.repository.TasksRepository;
import com.linkyoyo.reportaudit.repository.ExtractionTasksRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import javax.persistence.EntityManager;
import javax.transaction.Transactional;

import com.querydsl.jpa.impl.JPAQueryFactory;
import static com.linkyoyo.reportaudit.entity.QExtractionRules.extractionRules;
import static com.linkyoyo.reportaudit.entity.QCheckItems.checkItems;
import static com.linkyoyo.reportaudit.entity.QSysParaset.sysParaset;
import static com.linkyoyo.reportaudit.entity.QDocumentsExtraction.documentsExtraction;
import static com.linkyoyo.reportaudit.entity.QDocuments.documents;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.StringReader;
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
    private EntityManager entityManager;

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
    
    private JPAQueryFactory queryFactory;

    @Autowired
    private ObjectMapper objectMapper;
    
    @javax.annotation.PostConstruct
    public void init() {
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

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
                
                // 获取选中的抽取项
                List<Integer> selectedItems = parseSelectedItems(extractionTask.getSelectedItems());
                
                // 获取抽取规则
                List<ExtractionRules> rules = getExtractionRules(selectedItems);
                
                // 获取工作流配置
                WorkflowConfig config = getWorkflowConfig(extractionTask.getId(),"extraction");
                
                WorkflowResult result = new WorkflowResult();
                result.setTaskId(extractionTask.getId());
                result.setTaskType("extraction");
                result.setResults(new ArrayList<>());
                
                // 为每个抽取项执行工作流
                for (ExtractionRules rule : rules) {
                    try {

                        // 执行工作流前的config ，rule.agentPara 不为空，则设置为 配置项里面的参数配置
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
                
                // 获取选中的检查项
                List<Integer> selectedItems = parseSelectedItems(task.getSelectedItems());
                
                // 获取检查项
                List<CheckItems> checkItems = getCheckItems(selectedItems);
                
                // 获取工作流配置
                WorkflowConfig config = getWorkflowConfig(task.getId(),"check");
                
                WorkflowResult result = new WorkflowResult();
                result.setTaskId(task.getId());
                result.setTaskType("check");
                result.setResults(new ArrayList<>());
                
                // 为每个检查项执行工作流
                for (CheckItems checkItem : checkItems) {
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
                
                // 解析 rule.agentPara 中的配置
                WorkflowConfig ruleConfig = objectMapper.readValue(rule.getAgentPara(), WorkflowConfig.class);
                finalConfig = ruleConfig;
                
                log.info("成功应用 rule.agentPara 配置: ruleId={}, extractionUrl={}", 
                    rule.getId(), 
                    ruleConfig.getExtractionTemplate() != null ? ruleConfig.getExtractionTemplate().getUrl() : "null");
                    
            } catch (Exception e) {
                log.warn("解析 rule.agentPara 配置失败，使用默认配置: ruleId={}, error={}", 
                    rule.getId(), e.getMessage());
                // 解析失败时继续使用原始config
            }
        } else {
            log.debug("rule.agentPara 为空，使用默认配置: ruleId={}", rule.getId());
        }
        
        // 构建请求体
        Map<String, Object> requestBody = buildExtractionRequestBody(task, rule, filesText, finalConfig);
        
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
                
                // 解析 checkItem.agentPara 中的配置
                WorkflowConfig checkItemConfig = objectMapper.readValue(checkItem.getAgentPara(), WorkflowConfig.class);
                finalConfig = checkItemConfig;
                
                log.info("成功应用 checkItem.agentPara 配置: checkItemId={}, checkUrl={}", 
                    checkItem.getId(), 
                    checkItemConfig.getCheckTemplate() != null ? checkItemConfig.getCheckTemplate().getUrl() : "null");
                    
            } catch (Exception e) {
                log.warn("解析 checkItem.agentPara 配置失败，使用默认配置: checkItemId={}, error={}", 
                    checkItem.getId(), e.getMessage());
                // 解析失败时继续使用原始config
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
                // 调用原始事件处理器
                if (originalHandler != null) {
                    originalHandler.accept(event);
                }
                
                // 调用事件记录服务进行入库
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
                // 调用原始事件处理器
                if (originalHandler != null) {
                    originalHandler.accept(event);
                }
                
                // 调用事件记录服务进行入库
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
        
        // 使用 RestTemplate.execute 进行流式处理
        return restTemplate.execute(url, HttpMethod.POST, 
            // 请求回调：设置请求体和请求头
            clientHttpRequest -> {
                // 设置请求头
                clientHttpRequest.getHeaders().setContentType(MediaType.APPLICATION_JSON);
                clientHttpRequest.getHeaders().setBearerAuth(token);
                
                // 写入请求体
                try {
                    String requestBodyJson = objectMapper.writeValueAsString(requestBody);
                    clientHttpRequest.getBody().write(requestBodyJson.getBytes("UTF-8"));
                } catch (Exception e) {
                    log.error("写入请求体失败: {}", e.getMessage(), e);
                    throw new RuntimeException("写入请求体失败", e);
                }
            },
            // 响应提取器：处理流式响应
            clientHttpResponse -> {
                HttpStatus statusCode = clientHttpResponse.getStatusCode();
                
                if (statusCode == HttpStatus.OK) {
                    log.info("开始处理流式响应: itemId={}, itemName={}", itemId, itemName);
                    
                    // 直接处理流式响应
                    return processStreamResponseFromInputStream(
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
     * 处理流式响应（从InputStream直接处理）
     */
    private WorkflowItemResult processStreamResponseFromInputStream(
            java.io.InputStream inputStream,
            Integer itemId, 
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws IOException {
        
        WorkflowItemResult result = new WorkflowItemResult();
        result.setItemId(itemId);
        result.setItemName(itemName);
        result.setSuccess(true);
        
        StringBuilder outputBuilder = new StringBuilder();
        
        try (BufferedReader reader = new BufferedReader(new java.io.InputStreamReader(inputStream, "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("data: ")) {
                    String jsonData = line.substring(6);
                    if (!jsonData.trim().isEmpty() && !jsonData.equals("[DONE]")) {
                        try {
                            JsonNode eventNode = objectMapper.readTree(jsonData);
                            WorkflowEvent event = parseWorkflowEvent(eventNode);
                            
                            // 调用增强的事件处理器（包含入库功能）
                            if (eventHandler != null) {
                                eventHandler.accept(event);
                            }
                            
                            // 处理不同类型的事件
                            handleWorkflowEvent(event, result, outputBuilder);
                            
                        } catch (JsonProcessingException e) {
                            log.warn("解析工作流事件失败: {}", e.getMessage());
                        }
                    }
                }
            }
        }
        
        result.setOutput(outputBuilder.toString());
        return result;
    }

    /**
     * 处理流式响应（复用原有逻辑 - 保持向后兼容）
     */
    private WorkflowItemResult processStreamResponse(
            String responseBody, 
            Integer itemId, 
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws IOException {
        
        WorkflowItemResult result = new WorkflowItemResult();
        result.setItemId(itemId);
        result.setItemName(itemName);
        result.setSuccess(true);
        
        StringBuilder outputBuilder = new StringBuilder();
        
        try (BufferedReader reader = new BufferedReader(new StringReader(responseBody))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("data: ")) {
                    String jsonData = line.substring(6);
                    if (!jsonData.trim().isEmpty() && !jsonData.equals("[DONE]")) {
                        try {
                            JsonNode eventNode = objectMapper.readTree(jsonData);
                            WorkflowEvent event = parseWorkflowEvent(eventNode);
                            
                            // 调用增强的事件处理器（包含入库功能）
                            if (eventHandler != null) {
                                eventHandler.accept(event);
                            }
                            
                            // 处理不同类型的事件
                            handleWorkflowEvent(event, result, outputBuilder);
                            
                        } catch (JsonProcessingException e) {
                            log.warn("解析工作流事件失败: {}", e.getMessage());
                        }
                    }
                }
            }
        }
        
        result.setOutput(outputBuilder.toString());
        return result;
    }

    /**
     * 处理工作流事件（复用原有逻辑）
     */
    private void handleWorkflowEvent(WorkflowEvent event, WorkflowItemResult result, StringBuilder outputBuilder) {
        switch (event.getEvent()) {
            case "workflow_started":
                log.info("工作流开始（增强版）: workflowRunId={}", event.getWorkflowRunId());
                result.setWorkflowRunId(event.getWorkflowRunId());
                break;
                
            case "node_started":
                log.debug("节点开始: nodeId={}, title={}", 
                    event.getData().get("node_id"), event.getData().get("title"));
                break;
                
            case "node_finished":
                log.debug("节点完成: nodeId={}, status={}", 
                    event.getData().get("node_id"), event.getData().get("status"));
                
                // 收集输出内容
                Object outputs = event.getData().get("outputs");
                if (outputs != null) {
                    outputBuilder.append(outputs.toString()).append("\n");
                }
                break;
                
            case "workflow_finished":
                log.info("工作流完成（增强版）: workflowRunId={}, status={}", 
                    event.getWorkflowRunId(), event.getData().get("status"));
                
                // 提取最终结果
                Object finalOutputs = event.getData().get("outputs");
                if (finalOutputs != null) {
                    // 将最终结果保存到result中
                    result.setFinalOutput(finalOutputs.toString());
                    outputBuilder.append("=== 最终结果 ===\n");
                    outputBuilder.append(finalOutputs.toString()).append("\n");
                    log.info("工作流最终结果已保存（增强版）: itemId={}, itemName={}", 
                        result.getItemId(), result.getItemName());
                }

                Object totalTokens = event.getData().get("total_tokens");
                if (totalTokens != null) {
                    // 将最终结果保存到result中
                    result.setTotalTokens(Integer.parseInt( totalTokens.toString() ));

                }
                
                break;
                
            default:
                log.debug("未处理的工作流事件: {}", event.getEvent());
        }
    }

    /**
     * 解析工作流事件（复用原有逻辑）
     */
    private WorkflowEvent parseWorkflowEvent(JsonNode eventNode) {
        WorkflowEvent event = new WorkflowEvent();
        event.setEvent(eventNode.get("event").asText());
        event.setWorkflowRunId(eventNode.get("workflow_run_id").asText());
        event.setTaskId(eventNode.get("task_id").asText());
        
        JsonNode dataNode = eventNode.get("data");
        if (dataNode != null) {
            @SuppressWarnings("unchecked")
            Map<String, Object> data = objectMapper.convertValue(dataNode, Map.class);
            event.setData(data);
        }
        
        return event;
    }

    // 以下方法复用原有WorkflowProcessor的实现
    
    /**
     * 构建抽取任务请求体
     */
    private Map<String, Object> buildExtractionRequestBody(
            ExtractionTasks task, 
            ExtractionRules rule, 
            String filesText, 
            WorkflowConfig config) {
        
        Map<String, Object> inputs = new HashMap<>();
        inputs.put("taskId", task.getId());
        inputs.put("documentId", String.valueOf(task.getOriginalDocId()));
        inputs.put("files_text", filesText);
        inputs.put("extractRules", rule.getPromptTemplate());
        inputs.put("extractionId", String.valueOf(rule.getId()));
        inputs.put("checkBranch_1", "是");
        inputs.put("extractionName", rule.getRuleName());
        
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("files", new ArrayList<>());
        requestBody.put("inputs", inputs);
        requestBody.put("response_mode", "streaming");
        
        // 输出请求体到日志供调试
        try {
            String requestBodyJson = objectMapper.writeValueAsString(requestBody);
            log.info("抽取任务请求体（增强版）: {}", requestBodyJson);
        } catch (Exception e) {
            log.warn("输出请求体日志失败: {}", e.getMessage());
        }
        
        return requestBody;
    }

    /**
     * 构建检查任务请求体
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
        inputs.put("extractRules", checkItem.getPrompt()); // 使用检查项的prompt作为extractRules
        inputs.put("extractionId", String.valueOf(checkItem.getId())); // 使用检查项ID作为extractionId
        inputs.put("checkBranch_1", "是");
        inputs.put("extractionName", checkItem.getName()); // 使用检查项名称作为extractionName
        
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("files", new ArrayList<>());
        requestBody.put("inputs", inputs);
        requestBody.put("response_mode", "streaming");
        
        // 输出请求体到日志供调试
        try {
            String requestBodyJson = objectMapper.writeValueAsString(requestBody);
            log.info("检查任务请求体（增强版）: {}", requestBodyJson);
        } catch (Exception e) {
            log.warn("输出请求体日志失败: {}", e.getMessage());
        }
        
        return requestBody;
    }

    /**
     * 解析选中的项目ID列表
     */
    private List<Integer> parseSelectedItems(String selectedItemsJson) {
        if (selectedItemsJson == null || selectedItemsJson.trim().isEmpty()) {
            return new ArrayList<>();
        }
        
        try {
            JsonNode node = objectMapper.readTree(selectedItemsJson);
            List<Integer> items = new ArrayList<>();
            if (node.isArray()) {
                for (JsonNode item : node) {
                    items.add(item.asInt());
                }
            }
            return items;
        } catch (Exception e) {
            log.error("解析selectedItems失败: {}", e.getMessage());
            return new ArrayList<>();
        }
    }

    /**
     * 获取抽取规则
     */
    private List<ExtractionRules> getExtractionRules(List<Integer> ruleIds) {
        if (ruleIds.isEmpty()) {
            return new ArrayList<>();
        }
        
        return queryFactory
            .selectFrom(extractionRules)
            .where(extractionRules.id.in(ruleIds).and(extractionRules.delFlag.ne(true)))
            .fetch();
    }

    /**
     * 获取检查项
     */
    private List<CheckItems> getCheckItems(List<Integer> checkIds) {
        if (checkIds.isEmpty()) {
            return new ArrayList<>();
        }
        
        return queryFactory
            .selectFrom(checkItems)
            .where(checkItems.id.in(checkIds).and(checkItems.delFlag.ne(true)))
            .fetch();
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
            
            // 根据参数决定是否清空相关数据
            if (shouldClearData) {
                clearCheckTaskData(task.getId());
            } else {
                log.info("跳过数据清空，保留现有进度: taskId={}", task.getId());
            }
            
            // 获取选中的检查项
            List<Integer> selectedItems = parseSelectedItems(task.getSelectedItems());
            
            // 获取检查项（包含关联配置）
            List<CheckItems> checkItems = getCheckItems(selectedItems);
            
            // 获取工作流配置
            WorkflowConfig config = getWorkflowConfig(task.getId(),"check");
            
            WorkflowResult result = new WorkflowResult();
            result.setTaskId(task.getId());
            result.setTaskType("enhance_check");
            result.setResults(new ArrayList<>());
            
            // 为每个检查项执行增强版工作流
            for (CheckItems checkItem : checkItems) {
                try {
                    // 构建增强版的文件内容
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
            
            // 🔥 关键：增强版工作流执行完成后立即处理结果和入库操作
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
                
                // 将处理结果添加到WorkflowResult中，便于后续使用
                result.setProcessResult(processResult);
                
            } catch (Exception e) {
                log.error("处理增强版工作流结果异常: taskId={}, error={}", task.getId(), e.getMessage(), e);
                // 不影响主流程，继续返回原始结果
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
        
        // 1. 处理relationExtraction - 原文档抽取内容
        if (Boolean.TRUE.equals(checkItem.getRelationExtraction())) {
            List<Map<String, Object>> originalDocContents = getExtractionContentsByDocId(
                task.getOriginalDocId(), checkItem.getId());
            documentContents.addAll(originalDocContents);
        } else {
            // 如果不使用抽取内容，则使用原始文档的mdContent
            Map<String, Object> originalDocContent = getOriginalDocumentContent(task.getOriginalDocId());
            if (originalDocContent != null) {
                documentContents.add(originalDocContent);
            }
        }
        
        // 2. 处理relationReference - 参考文档抽取内容
        if (Boolean.TRUE.equals(checkItem.getRelationReference()) && task.getReferenceDocId() != null) {
            List<Integer> referenceDocIds = parseReferenceDocIds(task.getReferenceDocId());
            for (Integer refDocId : referenceDocIds) {
                List<Map<String, Object>> refDocContents = getExtractionContentsByDocId(
                    refDocId, checkItem.getId());
                documentContents.addAll(refDocContents);
            }
        }
        
        // 3. 处理relationStudy - 可研报告抽取内容
        if (Boolean.TRUE.equals(checkItem.getRelationStudy()) && task.getFeasibilityStudyReport() != null) {
            List<Map<String, Object>> studyDocContents = getExtractionContentsByDocId(
                task.getFeasibilityStudyReport(), checkItem.getId());
            documentContents.addAll(studyDocContents);
        }
        
        // 转换为JSON格式的字符串
        try {
            String result = objectMapper.writeValueAsString(documentContents);
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
            // 查询DocumentsExtraction表，通过ExtractionRules关联CheckItems
            List<DocumentsExtraction> extractions = queryFactory
                .selectFrom(documentsExtraction)
                .leftJoin(extractionRules).on(documentsExtraction.extractionRuleId.eq(extractionRules.id))
                .where(documentsExtraction.docId.eq(docId)
                    .and(extractionRules.refCheckItemId.eq(checkItemId))
                    .and(documentsExtraction.extractedContent.isNotNull()))
                .fetch();
            
            // 获取文档信息
            Documents document = queryFactory
                .selectFrom(documents)
                .where(documents.id.eq(docId))
                .fetchOne();
            
            String docName = document != null ? document.getOriginalFileName() : "未知文档";
            
            // 合并所有抽取内容
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
            Documents document = queryFactory
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
            JsonNode node = objectMapper.readTree(referenceDocIdJson);
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
     * 优先级：
     * 1. 先根据任务创建者获取对应的规则分类，从规则分类的 agent_para 获取配置
     * 2. 如果获取失败，则从 sysParaset 表获取默认配置
     */
    private WorkflowConfig getWorkflowConfig(String taskId) {
        return getWorkflowConfig(taskId, null);
    }
    
    /**
     * 获取工作流配置（支持任务类型区分）
     * 优先级：
     * 1. 先根据任务创建者获取对应的规则分类，从规则分类的 agent_para 获取配置
     * 2. 如果获取失败，则从 sysParaset 表获取默认配置
     * 
     * @param taskId 任务ID
     * @param taskType 任务类型（extraction/check），如果为null则自动检测
     */
    private WorkflowConfig getWorkflowConfig(String taskId, String taskType) {
        try {
            // 1. 尝试从规则分类获取配置
            String configJson = getConfigFromRuleClass(taskId, taskType);
            
            // 2. 如果规则分类配置为空，则从 sysParaset 获取默认配置
            if (configJson == null || configJson.trim().isEmpty()) {
                log.info("规则分类配置为空，使用默认配置: taskId={}, taskType={}", taskId, taskType);
                configJson = queryFactory
                    .select(sysParaset.agentPara)
                    .from(sysParaset)
                    .fetchFirst();
            }
            
            if (configJson == null || configJson.trim().isEmpty()) {
                throw new RuntimeException("未找到工作流配置数据");
            }
            
            return objectMapper.readValue(configJson, WorkflowConfig.class);
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
     * 
     * @param taskId 任务ID
     * @param taskType 任务类型（extraction/check），如果为null则自动检测
     */
    private String getConfigFromRuleClass(String taskId, String taskType) {
        try {
            Integer creater = null;
            
            // 根据任务类型从不同的表获取创建者信息
            if ("extraction".equals(taskType)) {
                // 从 extraction_tasks 表获取任务信息
                ExtractionTasks extractionTask = queryFactory
                    .selectFrom(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks)
                    .where(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks.id.eq(taskId))
                    .fetchOne();
                    
                if (extractionTask != null) {
                    creater = extractionTask.getCreater();
                    log.debug("从 extraction_tasks 表获取创建者: taskId={}, creater={}", taskId, creater);
                }
            } else if ("check".equals(taskType)) {
                // 从 tasks 表获取任务信息
                Tasks task = queryFactory
                    .selectFrom(com.linkyoyo.reportaudit.entity.QTasks.tasks)
                    .where(com.linkyoyo.reportaudit.entity.QTasks.tasks.id.eq(taskId))
                    .fetchOne();
                    
                if (task != null) {
                    creater = task.getCreater();
                    log.debug("从 tasks 表获取创建者: taskId={}, creater={}", taskId, creater);
                }
            } else {
                // 如果 taskType 为空或未知，先尝试从 extraction_tasks 表查询
                ExtractionTasks extractionTask = queryFactory
                    .selectFrom(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks)
                    .where(com.linkyoyo.reportaudit.entity.QExtractionTasks.extractionTasks.id.eq(taskId))
                    .fetchOne();
                    
                if (extractionTask != null) {
                    creater = extractionTask.getCreater();
                    log.debug("自动检测为 extraction 任务: taskId={}, creater={}", taskId, creater);
                } else {
                    // 如果 extraction_tasks 表中没有，再从 tasks 表查询
                    Tasks task = queryFactory
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
            
            // 根据创建者ID从数据库查询 SysOperator 对象
            SysOperator sysOperator = queryFactory
                .selectFrom(com.linkyoyo.reportaudit.entity.QSysOperator.sysOperator)
                .where(QSysOperator.sysOperator.id.eq(creater))
                .fetchOne();
                
            if (sysOperator == null) {
                log.warn("未找到创建者信息: creater={}", creater);
                return null;
            }
            
            // 获取规则分类
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
            // 强制设置任务状态为执行中并清空相关数据（重新执行）


            task.setStatus("started");
            task.setStartedAt(java.time.LocalDateTime.now());
            task.setProgress(BigDecimal.valueOf(0.00));
            task.setUpdatedAt(java.time.LocalDateTime.now());
            task = tasksRepository.save(task);


//            updateTaskStatus(taskId, "started", BigDecimal.ZERO, null);
            log.info("任务状态已强制设置为执行中: taskId={}", taskId);
            
            // 清空check_result和tasks_check_items数据
            clearCheckTaskData(taskId);
            log.info("已清空任务相关数据，准备重新执行: taskId={}", taskId);
            
            // 工作流开始时发送WebSocket消息
            taskProgressNotificationService.notifyTaskProgress(taskId, "check", "工作流开始执行", "");
            
            // 创建事件处理器来收集工作流事件并通过WebSocket发送
            Consumer<WorkflowEvent> eventHandler = event -> {
                String eventInfo = String.format("[%s] %s - %s", 
                    event.getEvent(), event.getWorkflowRunId(), event.getData());
                log.info("增强版工作流事件: {}", eventInfo);
                
                // 只在工作流结束时发送WebSocket消息
                if (event.getEvent().equals("workflow_finished") || event.getEvent().equals("workflow_failed")) {
                    String statusMessage = event.getEvent().equals("workflow_finished") ? "工作流执行完成" : "工作流执行失败";
                    taskProgressNotificationService.notifyTaskProgress(taskId, "check", statusMessage, "");
                }
            };
            
            // 执行增强版检查任务（同步）- 数据已在上面清空，这里不再清空
            WorkflowResult result = executeEnhanceCheckTaskSync(task, eventHandler, false);
            
            // 任务执行完成后的通知和状态更新
            if (result.isSuccess()) {
                log.info("增强版工作流任务执行成功: taskId={}, itemCount={}", 
                    taskId, result.getItemResults() != null ? result.getItemResults().size() : 0);
                
                // 更新任务完成时间
                task.setStatus("completed");
                task.setCompletedAt(java.time.LocalDateTime.now());
                task.setUpdatedAt(java.time.LocalDateTime.now());
                tasksRepository.save(task);
                
                taskProgressNotificationService.notifyTaskCompleted(taskId, "check", true);
            } else {
                log.error("增强版工作流任务执行失败: taskId={}, error={}", taskId, result.getErrorMessage());
                
                // 更新任务失败状态
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
     * @param taskId 任务ID
     * @param status 状态（queued, started, completed, failed等）
     * @param errorMessage 错误信息（可选）
     */
    private void updateTaskStatus(String taskId, String status, String errorMessage) {
        updateTaskStatus(taskId, status, null, errorMessage);
    }
    
    /**
     * 更新任务状态和进度
     * @param taskId 任务ID
     * @param status 状态（queued, started, completed, failed等）
     * @param progress 进度百分比（可选，null表示不更新进度）
     * @param errorMessage 错误信息（可选）
     */
    private void updateTaskStatus(String taskId, String status, BigDecimal progress, String errorMessage) {
        try {
            log.info("开始更新任务状态: taskId={}, status={}", taskId, status);
            
            Optional<com.linkyoyo.reportaudit.entity.Tasks> taskOpt = tasksRepository.findById(taskId);
            if (taskOpt.isPresent()) {
                com.linkyoyo.reportaudit.entity.Tasks task = taskOpt.get();
                log.info("找到任务，当前状态: taskId={}, currentStatus={}", taskId, task.getStatus());
                
                task.setStatus(status);
                
                // 只有在明确指定进度时才更新，避免覆盖TaskProgressNotificationService的动态计算
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
