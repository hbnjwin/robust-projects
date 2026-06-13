package com.linkyoyo.reportaudit.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.CheckItems;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.Tasks;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import javax.persistence.EntityManager;
import com.querydsl.jpa.impl.JPAQueryFactory;
import static com.linkyoyo.reportaudit.entity.QExtractionRules.extractionRules;
import static com.linkyoyo.reportaudit.entity.QCheckItems.checkItems;
import static com.linkyoyo.reportaudit.entity.QSysParaset.sysParaset;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.StringReader;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.function.Consumer;

/**
 * 工作流处理器
 * 负责处理抽取任务和检查任务的工作流调用
 */
@Slf4j
@Component
public class WorkflowProcessor {

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private RestTemplate restTemplate;
    
    private JPAQueryFactory queryFactory;

    private final ObjectMapper objectMapper = new ObjectMapper();
    
    @javax.annotation.PostConstruct
    public void init() {
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    /**
     * 处理抽取任务
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
                log.info("开始处理抽取任务: {}", extractionTask.getId());
                
                // 获取选中的抽取项
                List<Integer> selectedItems = parseSelectedItems(extractionTask.getSelectedItems());
                
                // 获取抽取规则
                List<ExtractionRules> rules = getExtractionRules(selectedItems);
                
                // 获取工作流配置
                WorkflowConfig config = getWorkflowConfig();
                
                WorkflowResult result = new WorkflowResult();
                result.setTaskId(extractionTask.getId());
                result.setTaskType("extraction");
                result.setResults(new ArrayList<>());
                
                // 为每个抽取项执行工作流
                for (ExtractionRules rule : rules) {
                    try {
                        WorkflowItemResult itemResult = executeExtractionWorkflow(
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
                
                log.info("抽取任务处理完成: {}", extractionTask.getId());
                return result;
                
            } catch (Exception e) {
                log.error("处理抽取任务失败: {}", e.getMessage(), e);
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
     * 处理检查任务
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
                log.info("开始处理检查任务: {}", task.getId());
                
                // 获取选中的检查项
                List<Integer> selectedItems = parseSelectedItems(task.getSelectedItems());
                
                // 获取检查项
                List<CheckItems> checkItems = getCheckItems(selectedItems);
                
                // 获取工作流配置
                WorkflowConfig config = getWorkflowConfig();
                
                WorkflowResult result = new WorkflowResult();
                result.setTaskId(task.getId());
                result.setTaskType("check");
                result.setResults(new ArrayList<>());
                
                // 为每个检查项执行工作流
                for (CheckItems checkItem : checkItems) {
                    try {
                        WorkflowItemResult itemResult = executeCheckWorkflow(
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
                
                log.info("检查任务处理完成: {}", task.getId());
                return result;
                
            } catch (Exception e) {
                log.error("处理检查任务失败: {}", e.getMessage(), e);
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
     * 执行抽取工作流
     */
    private WorkflowItemResult executeExtractionWorkflow(
            ExtractionTasks task, 
            ExtractionRules rule, 
            String filesText, 
            WorkflowConfig config,
            Consumer<WorkflowEvent> eventHandler) throws Exception {
        
        // 构建请求体
        Map<String, Object> requestBody = buildExtractionRequestBody(task, rule, filesText, config);
        
        // 执行工作流调用
        return executeWorkflowCall(
            config.getExtractionTemplate().getUrl(),
            config.getExtractionTemplate().getToken(),
            requestBody,
            rule.getId(),
            rule.getRuleName(),
            eventHandler
        );
    }

    /**
     * 执行检查工作流
     */
    private WorkflowItemResult executeCheckWorkflow(
            Tasks task, 
            CheckItems checkItem, 
            String filesText, 
            WorkflowConfig config,
            Consumer<WorkflowEvent> eventHandler) throws Exception {
        
        // 构建请求体
        Map<String, Object> requestBody = buildCheckRequestBody(task, checkItem, filesText, config);
        
        // 执行工作流调用
        return executeWorkflowCall(
            config.getCheckTemplate().getUrl(),
            config.getCheckTemplate().getToken(),
            requestBody,
            checkItem.getId(),
            checkItem.getName(),
            eventHandler
        );
    }

    /**
     * 执行工作流API调用
     */
    private WorkflowItemResult executeWorkflowCall(
            String url, 
            String token, 
            Map<String, Object> requestBody,
            Integer itemId,
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws Exception {
        
        // 设置请求头
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);
        
        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);
        
        log.info("调用工作流API: url={}, itemId={}, itemName={}", url, itemId, itemName);
        
        // 发送请求
        ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
        
        if (response.getStatusCode() == HttpStatus.OK) {
            String responseBody = response.getBody();
            return processStreamResponse(responseBody, itemId, itemName, eventHandler);
        } else {
            throw new RuntimeException("工作流调用失败: " + response.getStatusCode());
        }
    }

    /**
     * 处理流式响应
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
                            
                            // 调用事件处理器
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
     * 处理工作流事件
     */
    private void handleWorkflowEvent(WorkflowEvent event, WorkflowItemResult result, StringBuilder outputBuilder) {
        switch (event.getEvent()) {
            case "workflow_started":
                log.info("工作流开始: workflowRunId={}", event.getWorkflowRunId());
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
                log.info("工作流完成: workflowRunId={}, status={}", 
                    event.getWorkflowRunId(), event.getData().get("status"));
                
                // 提取最终结果
                Object finalOutputs = event.getData().get("outputs");
                if (finalOutputs != null) {
                    // 将最终结果保存到result中
                    result.setFinalOutput(finalOutputs.toString());
                    outputBuilder.append("=== 最终结果 ===\n");
                    outputBuilder.append(finalOutputs.toString()).append("\n");
                    log.info("工作流最终结果已保存: itemId={}, itemName={}", result.getItemId(), result.getItemName());
                }
                
                break;
                
            default:
                log.debug("未处理的工作流事件: {}", event.getEvent());
        }
    }

    /**
     * 解析工作流事件
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
            log.info("抽取任务请求体: {}", requestBodyJson);
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
        inputs.put("documentId", String.valueOf(task.getOriginalPath())); // Tasks表使用originalPath
        inputs.put("checkId", String.valueOf(checkItem.getId()));
        inputs.put("checkName", checkItem.getName());
        inputs.put("prompt", checkItem.getPrompt());
        inputs.put("files_text", filesText);
        
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("files", new ArrayList<>());
        requestBody.put("inputs", inputs);
        requestBody.put("response_mode", "streaming");
        
        // 输出请求体到日志供调试
        try {
            String requestBodyJson = objectMapper.writeValueAsString(requestBody);
            log.info("检查任务请求体: {}", requestBodyJson);
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
            .where(extractionRules.id.in(ruleIds))
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
            .where(checkItems.id.in(checkIds))
            .fetch();
    }

    /**
     * 从sysParaset表获取工作流配置
     */
    private WorkflowConfig getWorkflowConfig() {
        try {
            // 使用QueryDSL查询agent_para字段
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
