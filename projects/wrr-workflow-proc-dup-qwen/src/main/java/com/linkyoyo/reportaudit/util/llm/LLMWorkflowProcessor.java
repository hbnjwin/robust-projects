package com.linkyoyo.reportaudit.util.llm;

import com.linkyoyo.reportaudit.entity.CheckItems;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.service.WorkflowEventRecorderService;
import com.linkyoyo.reportaudit.util.WorkflowEvent;
import com.linkyoyo.reportaudit.util.WorkflowHelperService;
import com.linkyoyo.reportaudit.util.WorkflowItemResult;
import com.linkyoyo.reportaudit.util.WorkflowResult;
import com.linkyoyo.reportaudit.util.llm.model.LLMMessage;
import com.linkyoyo.reportaudit.util.llm.model.LLMResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import javax.annotation.PostConstruct;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.function.Consumer;
import java.util.stream.Collectors;

/**
 * LLM工作流处理器
 * 使用动态LLM服务替代传统工作流API调用，支持智能报告审计
 */
@Slf4j
@Component
public class LLMWorkflowProcessor {

    @Autowired
    private DynamicLLMService dynamicLLMService;

    @Autowired
    private WorkflowEventRecorderService eventRecorderService;

    @Autowired
    private WorkflowHelperService helperService;

    // 可配置的线程池参数
    @Value("${llm.workflow.thread-pool.core-size:4}")
    private int corePoolSize;

    @Value("${llm.workflow.thread-pool.max-size:8}")
    private int maxPoolSize;

    @Value("${llm.workflow.thread-pool.queue-capacity:100}")
    private int queueCapacity;

    // 自定义线程池
    private ExecutorService llmExecutorService;

    @PostConstruct
    public void init() {
        // 初始化自定义线程池
        this.llmExecutorService = new ThreadPoolExecutor(
            corePoolSize,
            maxPoolSize,
            60L, // keepAliveTime
            java.util.concurrent.TimeUnit.SECONDS,
            new java.util.concurrent.LinkedBlockingQueue<>(queueCapacity),
            r -> {
                Thread t = new Thread(r, "LLM-Worker-" + System.currentTimeMillis());
                t.setDaemon(true);
                return t;
            }
        );
        
        log.info("LLM工作流线程池初始化完成: coreSize={}, maxSize={}, queueCapacity={}", 
            corePoolSize, maxPoolSize, queueCapacity);
    }

    /**
     * 处理抽取任务（LLM版本）
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
                log.info("开始处理抽取任务（LLM版本）: {}", extractionTask.getId());

                // 发送任务开始事件
                sendWorkflowEvent(eventHandler, "workflow_started", extractionTask.getId(), 
                    Map.of("taskType", "extraction", "processor", "LLM"));

                // 获取选中的抽取项
                List<Integer> selectedItems = helperService.parseSelectedItems(extractionTask.getSelectedItems());

                // 获取抽取规则
                List<ExtractionRules> rules = helperService.getExtractionRules(selectedItems);

                WorkflowResult result = new WorkflowResult();
                result.setTaskId(extractionTask.getId());
                result.setTaskType("extraction");
                result.setResults(new ArrayList<>());

                // 并行执行所有抽取项的LLM处理（使用自定义线程池）
                List<CompletableFuture<WorkflowItemResult>> futures = rules.stream()
                    .map(rule -> CompletableFuture.supplyAsync(() -> {
                        try {
                            log.info("开始并行处理抽取项: ruleId={}, ruleName={}", rule.getId(), rule.getRuleName());
                            return executeExtractionWithLLM(extractionTask, rule, filesText, eventHandler);
                        } catch (Exception e) {
                            log.error("LLM处理抽取项失败: ruleId={}, error={}", rule.getId(), e.getMessage(), e);
                            return createErrorResult(rule.getId(), rule.getRuleName(), e.getMessage());
                        }
                    }, llmExecutorService))
                    .collect(Collectors.toList());

                // 等待所有抽取项完成
                log.info("等待{}个抽取项并行处理完成", futures.size());
                List<WorkflowItemResult> itemResults = futures.stream()
                    .map(CompletableFuture::join)
                    .collect(Collectors.toList());
                
                result.getResults().addAll(itemResults);
                log.info("所有抽取项并行处理完成: 总数={}, 成功={}", 
                    itemResults.size(), 
                    itemResults.stream().mapToInt(r -> r.isSuccess() ? 1 : 0).sum());

                // 发送任务完成事件
                sendWorkflowEvent(eventHandler, "workflow_finished", extractionTask.getId(),
                    Map.of("success", result.isSuccess(), "totalItems", result.getResults().size()));

                log.info("抽取任务处理完成（LLM版本）: taskId={}, 成功项数={}", 
                    extractionTask.getId(), result.getResults().stream().mapToInt(r -> r.isSuccess() ? 1 : 0).sum());

                return result;

            } catch (Exception e) {
                log.error("LLM抽取任务处理失败: taskId={}, error={}", extractionTask.getId(), e.getMessage(), e);
                WorkflowResult errorResult = new WorkflowResult();
                errorResult.setTaskId(extractionTask.getId());
                errorResult.setTaskType("extraction");
                errorResult.setSuccess(false);
                errorResult.setError(e.getMessage());
                errorResult.setResults(new ArrayList<>());
                return errorResult;
            }
        }, llmExecutorService); // 使用自定义线程池
    }

    /**
     * 处理检查任务（LLM版本）
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
                log.info("开始处理检查任务（LLM版本）: {}", task.getId());

                // 发送任务开始事件
                sendWorkflowEvent(eventHandler, "workflow_started", task.getId(),
                    Map.of("taskType", "check", "processor", "LLM"));

                // 获取选中的检查项
                List<Integer> selectedItems = helperService.parseSelectedItems(task.getSelectedItems());

                // 获取检查规则
                List<CheckItems> checkItems = helperService.getCheckItems(selectedItems);

                WorkflowResult result = new WorkflowResult();
                result.setTaskId(task.getId());
                result.setTaskType("check");
                result.setResults(new ArrayList<>());

                // 并行执行所有检查项的LLM处理（使用自定义线程池）
                List<CompletableFuture<WorkflowItemResult>> futures = checkItems.stream()
                    .map(checkItem -> CompletableFuture.supplyAsync(() -> {
                        try {
                            log.info("开始并行处理检查项: checkItemId={}, checkItemName={}", checkItem.getId(), checkItem.getName());
                            return executeCheckWithLLM(task, checkItem, filesText, eventHandler);
                        } catch (Exception e) {
                            log.error("LLM处理检查项失败: checkItemId={}, error={}", checkItem.getId(), e.getMessage(), e);
                            return createErrorResult(checkItem.getId(), checkItem.getName(), e.getMessage());
                        }
                    }, llmExecutorService))
                    .collect(Collectors.toList());

                // 等待所有检查项完成
                log.info("等待{}个检查项并行处理完成", futures.size());
                List<WorkflowItemResult> itemResults = futures.stream()
                    .map(CompletableFuture::join)
                    .collect(Collectors.toList());
                
                result.getResults().addAll(itemResults);
                log.info("所有检查项并行处理完成: 总数={}, 成功={}", 
                    itemResults.size(), 
                    itemResults.stream().mapToInt(r -> r.isSuccess() ? 1 : 0).sum());

                // 发送任务完成事件
                sendWorkflowEvent(eventHandler, "workflow_finished", task.getId(),
                    Map.of("success", result.isSuccess(), "totalItems", result.getResults().size()));

                log.info("检查任务处理完成（LLM版本）: taskId={}, 成功项数={}", 
                    task.getId(), result.getResults().stream().mapToInt(r -> r.isSuccess() ? 1 : 0).sum());

                return result;

            } catch (Exception e) {
                log.error("LLM检查任务处理失败: taskId={}, error={}", task.getId(), e.getMessage(), e);
                WorkflowResult errorResult = new WorkflowResult();
                errorResult.setTaskId(task.getId());
                errorResult.setTaskType("check");
                errorResult.setSuccess(false);
                errorResult.setError(e.getMessage());
                errorResult.setResults(new ArrayList<>());
                return errorResult;
            }
        }, llmExecutorService); // 使用自定义线程池
    }

    /**
     * 处理单个检查项（LLM版本，单线程）
     * @param task 检查任务实体
     * @param checkItem 检查项
     * @param filesText 文档内容
     * @param eventHandler 事件处理器
     * @return 处理结果
     */
    public WorkflowItemResult processSingleCheckItem(
            Tasks task,
            CheckItems checkItem,
            String filesText,
            Consumer<WorkflowEvent> eventHandler) {
        
        log.info("开始处理单个检查项（LLM版本，单线程）: checkItemId={}, checkItemName={}", checkItem.getId(), checkItem.getName());
        
        try {
            // 发送节点开始事件
            sendWorkflowEvent(eventHandler, "node_started", task.getId(),
                Map.of("checkItemId", checkItem.getId(), "checkItemName", checkItem.getName()));

            // 执行检查项处理
            WorkflowItemResult itemResult = executeCheckWithLLM(task, checkItem, filesText, eventHandler);
            
            // 发送节点完成事件
            sendWorkflowEvent(eventHandler, "node_finished", task.getId(),
                Map.of("checkItemId", checkItem.getId(), "success", itemResult.isSuccess(),
                       "elapsedTime", itemResult.getElapsedTime()));

            log.info("单个检查项处理完成（LLM版本，单线程）: checkItemId={}, success={}", checkItem.getId(), itemResult.isSuccess());
            return itemResult;

        } catch (Exception e) {
            log.error("处理单个检查项失败: checkItemId={}, error={}", checkItem.getId(), e.getMessage(), e);
            return createErrorResult(checkItem.getId(), checkItem.getName(), e.getMessage());
        }
    }

    /**
     * 使用LLM执行抽取项处理
     */
    private WorkflowItemResult executeExtractionWithLLM(
            ExtractionTasks task,
            ExtractionRules rule,
            String filesText,
            Consumer<WorkflowEvent> eventHandler) {

        long startTime = System.currentTimeMillis();
        String workflowRunId = "llm-extraction-" + task.getId() + "-" + rule.getId() + "-" + startTime;

        WorkflowItemResult itemResult = new WorkflowItemResult();
        itemResult.setItemId(rule.getId());
        itemResult.setItemName(rule.getRuleName());
        itemResult.setWorkflowRunId(workflowRunId);
        itemResult.setStartTime(startTime);

        try {
            // 1. 执行前创建 extraction_tasks_items 记录
            WorkflowEvent startedEvent = createStartedEvent(task.getId(), workflowRunId);
            eventRecorderService.handleExtractionWorkflowEvent(startedEvent, 
                task.getId(), rule.getId(), rule.getRuleName(), 
                task.getOriginalDocId() != null ? task.getOriginalDocId().toString() : "");
            log.info("已创建抽取项执行记录: ruleId={}, ruleName={}", rule.getId(), rule.getRuleName());

            // 2. 构建LLM消息
            List<LLMMessage> messages = buildExtractionMessages(rule, filesText);

            // 3. 调用LLM服务
            log.info("调用LLM处理抽取项: ruleId={}, ruleName={}", rule.getId(), rule.getRuleName());
            
            // 添加详细的消息内容日志用于对比
            log.info("=== EXTRACTION接口LLM消息内容 ===");
            for (int i = 0; i < messages.size(); i++) {
                LLMMessage msg = messages.get(i);
                log.info("消息{}[{}]: {}", i+1, msg.getRole(), 
                    msg.getContent().length() > 500 ? msg.getContent().substring(0, 500) + "..." : msg.getContent());
            }
            log.info("=== 消息内容结束 ===");
            
            LLMResponse llmResponse = dynamicLLMService.chatCompletion(messages, null, null, null);

            long endTime = System.currentTimeMillis();
            itemResult.setEndTime(endTime);
            itemResult.setElapsedTime((endTime - startTime) / 1000.0);

            if (llmResponse.isSuccess()) {
                itemResult.setSuccess(true);
                itemResult.setFinalOutput(llmResponse.getContent());
                itemResult.setOutput(llmResponse.getContent());

                // 创建工作流事件并使用事件记录服务存储结果
                WorkflowEvent completedEvent = createCompletedEvent(task.getId(), workflowRunId, llmResponse.getContent());
                eventRecorderService.handleExtractionWorkflowEvent(completedEvent, 
                    task.getId(), rule.getId(), rule.getRuleName(), 
                    task.getOriginalDocId() != null ? task.getOriginalDocId().toString() : "");

                log.info("LLM抽取项处理成功: ruleId={}, 耗时={}秒", rule.getId(), itemResult.getElapsedTime());
            } else {
                itemResult.setSuccess(false);
                itemResult.setError(llmResponse.getError());
                
                // 创建失败事件并记录
                WorkflowEvent failedEvent = createFailedEvent(task.getId(), workflowRunId, llmResponse.getError());
                eventRecorderService.handleExtractionWorkflowEvent(failedEvent, 
                    task.getId(), rule.getId(), rule.getRuleName(), 
                    task.getOriginalDocId() != null ? task.getOriginalDocId().toString() : "");
                
                log.error("LLM抽取项处理失败: ruleId={}, error={}", rule.getId(), llmResponse.getError());
            }

        } catch (Exception e) {
            long endTime = System.currentTimeMillis();
            itemResult.setEndTime(endTime);
            itemResult.setElapsedTime((endTime - startTime) / 1000.0);
            itemResult.setSuccess(false);
            itemResult.setError("LLM调用异常: " + e.getMessage());
            
            // 记录异常状态
            try {
                WorkflowEvent errorEvent = createFailedEvent(task.getId(), workflowRunId, "LLM调用异常: " + e.getMessage());
                eventRecorderService.handleExtractionWorkflowEvent(errorEvent, 
                    task.getId(), rule.getId(), rule.getRuleName(), 
                    task.getOriginalDocId() != null ? task.getOriginalDocId().toString() : "");
            } catch (Exception recordException) {
                log.error("记录异常状态失败: {}", recordException.getMessage());
            }
            
            log.error("LLM抽取项处理异常: ruleId={}, error={}", rule.getId(), e.getMessage(), e);
        }

        return itemResult;
    }

    /**
     * 使用LLM执行检查项处理
     */
    private WorkflowItemResult executeCheckWithLLM(
            Tasks task,
            CheckItems checkItem,
            String filesText,
            Consumer<WorkflowEvent> eventHandler) {

        long startTime = System.currentTimeMillis();
        String workflowRunId = "llm-check-" + task.getId() + "-" + checkItem.getId() + "-" + startTime;

        WorkflowItemResult itemResult = new WorkflowItemResult();
        itemResult.setItemId(checkItem.getId());
        itemResult.setItemName(checkItem.getName());
        itemResult.setWorkflowRunId(workflowRunId);
        itemResult.setStartTime(startTime);

        try {
            // 1. 执行前创建 tasks_check_items 记录
            WorkflowEvent startedEvent = createStartedEvent(task.getId(), workflowRunId);
            eventRecorderService.handleCheckWorkflowEvent(startedEvent, 
                task.getId(), checkItem.getId(), checkItem.getName(), 
                task.getOriginalDocId() != null ? task.getOriginalDocId().toString() : "");
            log.info("已创建检查项执行记录: checkItemId={}, checkItemName={}", checkItem.getId(), checkItem.getName());

            // 2. 发送节点开始事件
            sendWorkflowEvent(eventHandler, "node_started", task.getId(),
                Map.of("checkItemId", checkItem.getId(), "checkItemName", checkItem.getName(), "workflowRunId", workflowRunId));

            // 3. 构建LLM消息
            List<LLMMessage> messages = buildCheckMessages(checkItem, filesText);

            // 4. 调用LLM服务
            log.info("调用LLM处理检查项: checkItemId={}, checkItemName={}", checkItem.getId(), checkItem.getName());
            LLMResponse llmResponse = dynamicLLMService.chatCompletion(messages, null, null, null);

            long endTime = System.currentTimeMillis();
            itemResult.setEndTime(endTime);
            itemResult.setElapsedTime((endTime - startTime) / 1000.0);

            if (llmResponse.isSuccess()) {
                itemResult.setSuccess(true);
                itemResult.setFinalOutput(llmResponse.getContent());
                itemResult.setOutput(llmResponse.getContent());

                // 记录检查结果到数据库
                recordCheckResult(task.getId(), checkItem, llmResponse, workflowRunId);

                log.info("LLM检查项处理成功: checkItemId={}, 耗时={}秒", checkItem.getId(), itemResult.getElapsedTime());
            } else {
                itemResult.setSuccess(false);
                itemResult.setError(llmResponse.getError());
                log.error("LLM检查项处理失败: checkItemId={}, error={}", checkItem.getId(), llmResponse.getError());
            }

            // 发送节点完成事件
            sendWorkflowEvent(eventHandler, "node_finished", task.getId(),
                Map.of("checkItemId", checkItem.getId(), "success", itemResult.isSuccess(),
                       "workflowRunId", workflowRunId, "elapsedTime", itemResult.getElapsedTime()));

        } catch (Exception e) {
            long endTime = System.currentTimeMillis();
            itemResult.setEndTime(endTime);
            itemResult.setElapsedTime((endTime - startTime) / 1000.0);
            itemResult.setSuccess(false);
            itemResult.setError("LLM调用异常: " + e.getMessage());
            log.error("LLM检查项处理异常: checkItemId={}, error={}", checkItem.getId(), e.getMessage(), e);
        }

        return itemResult;
    }

    /**
     * 构建抽取任务的LLM消息
     */
    private List<LLMMessage> buildExtractionMessages(ExtractionRules rule, String filesText) {
        List<LLMMessage> messages = new ArrayList<>();

        // 系统消息 - 设定角色和任务
        String systemPrompt = "你是一个专业的文档信息抽取助手。请根据给定的抽取规则，从文档中准确抽取相关信息。" +
                "请以结构化的格式返回抽取结果，确保信息的准确性和完整性。";
        messages.add(LLMMessage.system(systemPrompt));

        // 用户消息 - 包含抽取规则和文档内容
        StringBuilder userPrompt = new StringBuilder();
        userPrompt.append("抽取规则名称: ").append(rule.getRuleName()).append("\n");
        
        if (StringUtils.hasText(rule.getRuleDescription())) {
            userPrompt.append("规则描述: ").append(rule.getRuleDescription()).append("\n");
        }
        
        if (StringUtils.hasText(rule.getPromptTemplate())) {
            userPrompt.append("抽取要求: ").append(rule.getPromptTemplate()).append("\n");
        }
        
        userPrompt.append("\n文档内容:\n").append(filesText);
        
        messages.add(LLMMessage.user(userPrompt.toString()));

        return messages;
    }

    /**
     * 构建检查任务的LLM消息
     */
    private List<LLMMessage> buildCheckMessages(CheckItems checkItem, String filesText) {
        List<LLMMessage> messages = new ArrayList<>();

        // 系统消息 - 设定角色和任务
        String systemPrompt = "你是一个专业的文档合规检查助手。请根据给定的检查规则，对文档内容进行详细检查。" +
                "请指出发现的问题、风险点或不合规之处，并提供具体的改进建议。";
        messages.add(LLMMessage.system(systemPrompt));

        // 用户消息 - 包含检查规则和文档内容
        StringBuilder userPrompt = new StringBuilder();
        userPrompt.append("检查项名称: ").append(checkItem.getName()).append("\n");
        
        if (StringUtils.hasText(checkItem.getDescription())) {
            userPrompt.append("检查描述: ").append(checkItem.getDescription()).append("\n");
        }
        
        if (StringUtils.hasText(checkItem.getPrompt())) {
            userPrompt.append("检查要求: ").append(checkItem.getPrompt()).append("\n");
        }
        
        userPrompt.append("\n文档内容:\n").append(filesText);
        
        messages.add(LLMMessage.user(userPrompt.toString()));

        return messages;
    }

    /**
     * 记录抽取结果到数据库
     */
    private void recordExtractionResult(String taskId, ExtractionRules rule, LLMResponse llmResponse, String workflowRunId) {
        try {
            // 创建工作流事件并使用事件记录服务存储结果
            WorkflowEvent completedEvent = createCompletedEvent(taskId, workflowRunId, llmResponse.getContent());
            eventRecorderService.handleExtractionWorkflowEvent(completedEvent, 
                taskId, rule.getId(), rule.getRuleName(), taskId);
            
            log.debug("抽取结果已记录: taskId={}, ruleId={}", taskId, rule.getId());
        } catch (Exception e) {
            log.error("记录抽取结果失败: taskId={}, ruleId={}, error={}", taskId, rule.getId(), e.getMessage(), e);
        }
    }

    /**
     * 记录检查结果到数据库
     */
    private void recordCheckResult(String taskId, CheckItems checkItem, LLMResponse llmResponse, String workflowRunId) {
        try {
                // 创建工作流事件并使用事件记录服务存储结果
                WorkflowEvent completedEvent = createCompletedEvent(taskId, workflowRunId, llmResponse.getContent());
                eventRecorderService.handleCheckWorkflowEvent(completedEvent, 
                    taskId, checkItem.getId(), checkItem.getName(), 
                    taskId != null ? taskId.toString() : "");
            
            log.debug("检查结果已记录: taskId={}, checkItemId={}", taskId, checkItem.getId());
        } catch (Exception e) {
            log.error("记录检查结果失败: taskId={}, checkItemId={}, error={}", taskId, checkItem.getId(), e.getMessage(), e);
        }
    }

    /**
     * 创建错误结果
     */
    private WorkflowItemResult createErrorResult(Integer itemId, String itemName, String error) {
        WorkflowItemResult errorResult = new WorkflowItemResult();
        errorResult.setItemId(itemId);
        errorResult.setItemName(itemName);
        errorResult.setSuccess(false);
        errorResult.setError(error);
        errorResult.setStartTime(System.currentTimeMillis());
        errorResult.setEndTime(System.currentTimeMillis());
        errorResult.setElapsedTime(0.0);
        return errorResult;
    }

    /**
     * 创建开始事件
     */
    private WorkflowEvent createStartedEvent(String taskId, String workflowRunId) {
        WorkflowEvent event = new WorkflowEvent();
        event.setEvent("workflow_started");
        event.setTaskId(taskId);
        event.setWorkflowRunId(workflowRunId);
        
        Map<String, Object> data = new HashMap<>();
        data.put("status", "running");
        event.setData(data);
        
        return event;
    }

    /**
     * 创建完成事件
     */
    private WorkflowEvent createCompletedEvent(String taskId, String workflowRunId, String output) {
        WorkflowEvent event = new WorkflowEvent();
        event.setEvent("workflow_finished");
        event.setTaskId(taskId);
        event.setWorkflowRunId(workflowRunId);
        
        Map<String, Object> data = new HashMap<>();
        data.put("status", "succeeded");
        data.put("outputs", output);
        event.setData(data);
        
        return event;
    }

    /**
     * 创建失败事件
     */
    private WorkflowEvent createFailedEvent(String taskId, String workflowRunId, String error) {
        WorkflowEvent event = new WorkflowEvent();
        event.setEvent("workflow_finished");
        event.setTaskId(taskId);
        event.setWorkflowRunId(workflowRunId);
        
        Map<String, Object> data = new HashMap<>();
        data.put("status", "failed");
        data.put("error", error);
        event.setData(data);
        
        return event;
    }

    /**
     * 发送工作流事件
     */
    private void sendWorkflowEvent(Consumer<WorkflowEvent> eventHandler, String eventType, String taskId, Map<String, Object> data) {
        if (eventHandler != null) {
            try {
                WorkflowEvent event = new WorkflowEvent();
                event.setEvent(eventType);
                event.setTaskId(taskId);
                event.setData(data);
                eventHandler.accept(event);
            } catch (Exception e) {
                log.warn("发送工作流事件失败: eventType={}, taskId={}, error={}", eventType, taskId, e.getMessage());
            }
        }
    }
}
