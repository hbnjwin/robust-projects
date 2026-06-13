package com.linkyoyo.reportaudit.util;

import com.linkyoyo.reportaudit.entity.CheckItems;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.Tasks;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

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
    private RestTemplate restTemplate;

    @Autowired
    private WorkflowQueryHelper queryHelper;

    @Autowired
    private WorkflowSSEHelper sseHelper;

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

                List<Integer> selectedItems = queryHelper.parseSelectedItems(extractionTask.getSelectedItems());
                List<ExtractionRules> rules = queryHelper.getExtractionRules(selectedItems);
                WorkflowConfig config = queryHelper.getDefaultWorkflowConfig();

                WorkflowResult result = new WorkflowResult();
                result.setTaskId(extractionTask.getId());
                result.setTaskType("extraction");
                result.setResults(new ArrayList<>());

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

                List<Integer> selectedItems = queryHelper.parseSelectedItems(task.getSelectedItems());
                List<CheckItems> checkItemsList = queryHelper.getCheckItems(selectedItems);
                WorkflowConfig config = queryHelper.getDefaultWorkflowConfig();

                WorkflowResult result = new WorkflowResult();
                result.setTaskId(task.getId());
                result.setTaskType("check");
                result.setResults(new ArrayList<>());

                for (CheckItems checkItem : checkItemsList) {
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

        Map<String, Object> requestBody = sseHelper.buildExtractionRequestBody(task, rule, filesText, config);

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

        Map<String, Object> requestBody = buildCheckRequestBody(task, checkItem, filesText, config);

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

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(requestBody, headers);

        log.info("调用工作流API: url={}, itemId={}, itemName={}", url, itemId, itemName);

        ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);

        if (response.getStatusCode() == HttpStatus.OK) {
            String responseBody = response.getBody();
            return sseHelper.processStreamResponse(responseBody, itemId, itemName, eventHandler);
        } else {
            throw new RuntimeException("工作流调用失败: " + response.getStatusCode());
        }
    }

    /**
     * 构建检查任务请求体（WP特有字段映射）
     */
    private Map<String, Object> buildCheckRequestBody(
            Tasks task,
            CheckItems checkItem,
            String filesText,
            WorkflowConfig config) {

        Map<String, Object> inputs = new HashMap<>();
        inputs.put("taskId", task.getId());
        inputs.put("documentId", String.valueOf(task.getOriginalPath()));
        inputs.put("checkId", String.valueOf(checkItem.getId()));
        inputs.put("checkName", checkItem.getName());
        inputs.put("prompt", checkItem.getPrompt());
        inputs.put("files_text", filesText);

        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("files", new ArrayList<>());
        requestBody.put("inputs", inputs);
        requestBody.put("response_mode", "streaming");

        try {
            String requestBodyJson = queryHelper.getObjectMapper().writeValueAsString(requestBody);
            log.info("检查任务请求体: {}", requestBodyJson);
        } catch (Exception e) {
            log.warn("输出请求体日志失败: {}", e.getMessage());
        }

        return requestBody;
    }
}
