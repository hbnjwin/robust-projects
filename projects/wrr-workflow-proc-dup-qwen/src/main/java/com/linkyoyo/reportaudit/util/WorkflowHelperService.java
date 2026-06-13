package com.linkyoyo.reportaudit.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.CheckItems;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import javax.persistence.EntityManager;
import com.querydsl.jpa.impl.JPAQueryFactory;
import static com.linkyoyo.reportaudit.entity.QExtractionRules.extractionRules;
import static com.linkyoyo.reportaudit.entity.QCheckItems.checkItems;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.Reader;
import java.util.*;
import java.util.function.Consumer;

/**
 * 工作流共享服务类
 * 提供三个工作流处理器（WorkflowProcessor、EnhancedWorkflowProcessor、LLMWorkflowProcessor）
 * 共用的数据查询、SSE流解析、事件处理和请求体构建方法，消除重复代码。
 */
@Slf4j
@Component
public class WorkflowHelperService {

    @Autowired
    private EntityManager entityManager;

    private JPAQueryFactory queryFactory;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @javax.annotation.PostConstruct
    public void init() {
        this.queryFactory = new JPAQueryFactory(entityManager);
    }

    // ==================== 数据查询方法 ====================

    /**
     * 解析选中项目字符串为ID列表
     * 支持多种格式：
     * 1. 数组格式：[1, 3, 5] 或 [1,3,5]
     * 2. 逗号分隔：1,3,5 或 1, 3, 5
     * 3. 单个数字：5
     */
    public List<Integer> parseSelectedItems(String selectedItems) {
        List<Integer> itemIds = new ArrayList<>();
        if (selectedItems != null && !selectedItems.trim().isEmpty()) {
            try {
                // 移除数组括号和空格，统一处理
                String cleanedItems = selectedItems.trim()
                    .replaceAll("^\\[", "")  // 移除开头的 [
                    .replaceAll("\\]$", "")  // 移除结尾的 ]
                    .replaceAll("\\s+", ""); // 移除所有空格

                if (!cleanedItems.isEmpty()) {
                    String[] items = cleanedItems.split(",");
                    for (String item : items) {
                        if (!item.trim().isEmpty()) {
                            itemIds.add(Integer.parseInt(item.trim()));
                        }
                    }
                }

                log.debug("解析选中项目成功: selectedItems={} -> itemIds={}", selectedItems, itemIds);
            } catch (Exception e) {
                log.error("解析选中项目失败: selectedItems={}, error={}", selectedItems, e.getMessage());
                // 返回空列表而不是抛出异常，保证程序继续运行
            }
        }
        return itemIds;
    }

    /**
     * 获取抽取规则列表
     * 过滤已删除记录（delFlag为null或false），按优先级降序、ID升序排列
     */
    public List<ExtractionRules> getExtractionRules(List<Integer> ruleIds) {
        if (ruleIds == null || ruleIds.isEmpty()) {
            return new ArrayList<>();
        }

        return queryFactory.selectFrom(extractionRules)
                .where(extractionRules.id.in(ruleIds)
                        .and(extractionRules.delFlag.isNull().or(extractionRules.delFlag.eq(false))))
                .orderBy(extractionRules.priority.desc(), extractionRules.id.asc())
                .fetch();
    }

    /**
     * 获取检查项列表
     * 过滤已删除记录（delFlag为null或false），按序号升序、ID升序排列
     */
    public List<CheckItems> getCheckItems(List<Integer> checkIds) {
        if (checkIds == null || checkIds.isEmpty()) {
            return new ArrayList<>();
        }

        return queryFactory.selectFrom(checkItems)
                .where(checkItems.id.in(checkIds)
                        .and(checkItems.delFlag.isNull().or(checkItems.delFlag.eq(false))))
                .orderBy(checkItems.sequence.asc(), checkItems.id.asc())
                .fetch();
    }

    // ==================== SSE流解析与事件处理 ====================

    /**
     * 解析工作流事件（从JSON节点构建WorkflowEvent对象）
     */
    public WorkflowEvent parseWorkflowEvent(JsonNode eventNode) {
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
     * 处理工作流事件（根据事件类型更新结果和输出）
     * 支持：workflow_started、node_started、node_finished、workflow_finished
     */
    public void handleWorkflowEvent(WorkflowEvent event, WorkflowItemResult result, StringBuilder outputBuilder) {
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
                    result.setFinalOutput(finalOutputs.toString());
                    outputBuilder.append("=== 最终结果 ===\n");
                    outputBuilder.append(finalOutputs.toString()).append("\n");
                    log.info("工作流最终结果已保存: itemId={}, itemName={}",
                        result.getItemId(), result.getItemName());
                }

                // 提取token用量（如果存在）
                Object totalTokens = event.getData().get("total_tokens");
                if (totalTokens != null) {
                    result.setTotalTokens(Integer.parseInt(totalTokens.toString()));
                }

                break;

            default:
                log.debug("未处理的工作流事件: {}", event.getEvent());
        }
    }

    /**
     * 处理SSE流式响应
     * 接受Reader参数，调用方可以传入StringReader（非流式）或InputStreamReader（真流式）
     *
     * @param inputReader 输入源（StringReader或InputStreamReader）
     * @param itemId 当前处理项ID
     * @param itemName 当前处理项名称
     * @param eventHandler 外部事件处理器（可为null）
     * @return 处理结果
     */
    public WorkflowItemResult processSSEStream(
            Reader inputReader,
            Integer itemId,
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws IOException {

        WorkflowItemResult result = new WorkflowItemResult();
        result.setItemId(itemId);
        result.setItemName(itemName);
        result.setSuccess(true);

        StringBuilder outputBuilder = new StringBuilder();

        try (BufferedReader reader = new BufferedReader(inputReader)) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.startsWith("data: ")) {
                    String jsonData = line.substring(6);
                    if (!jsonData.trim().isEmpty() && !jsonData.equals("[DONE]")) {
                        try {
                            JsonNode eventNode = objectMapper.readTree(jsonData);
                            WorkflowEvent event = parseWorkflowEvent(eventNode);

                            // 调用外部事件处理器
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

    // ==================== 请求体构建 ====================

    /**
     * 构建抽取任务请求体
     */
    public Map<String, Object> buildExtractionRequestBody(
            ExtractionTasks task,
            ExtractionRules rule,
            String filesText) {

        Map<String, Object> inputs = new HashMap<>();
        inputs.put("taskId", task.getId());
        inputs.put("documentId", String.valueOf(task.getOriginalDocId()));
        inputs.put("files_text", filesText);
        inputs.put("extractRules", rule.getPromptTemplate());
        inputs.put("extractionId", String.valueOf(rule.getId()));
        inputs.put("checkBranch_1", "是");
        inputs.put("extractionName", rule.getRuleName());

        return buildRequestBodyWrapper(inputs);
    }

    /**
     * 构建请求体外层包装（files、inputs、response_mode）
     * 供各处理器在构建检查任务请求体时复用
     *
     * @param inputs 已构建好的inputs map
     * @return 完整的请求体map
     */
    public Map<String, Object> buildRequestBodyWrapper(Map<String, Object> inputs) {
        Map<String, Object> requestBody = new HashMap<>();
        requestBody.put("files", new ArrayList<>());
        requestBody.put("inputs", inputs);
        requestBody.put("response_mode", "streaming");

        // 输出请求体到日志供调试
        try {
            String requestBodyJson = objectMapper.writeValueAsString(requestBody);
            log.info("工作流请求体: {}", requestBodyJson);
        } catch (Exception e) {
            log.warn("输出请求体日志失败: {}", e.getMessage());
        }

        return requestBody;
    }
}
