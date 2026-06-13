package com.linkyoyo.reportaudit.util;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.ExtractionRules;
import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.function.Consumer;

/**
 * 工作流SSE流解析Helper
 * 集中管理WorkflowProcessor和EnhancedWorkflowProcessor共用的SSE解析与请求体构建逻辑
 */
@Slf4j
@Component
public class WorkflowSSEHelper {

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 解析工作流事件JSON节点
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
     * 处理工作流事件（含total_tokens提取）
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

                Object outputs = event.getData().get("outputs");
                if (outputs != null) {
                    outputBuilder.append(outputs.toString()).append("\n");
                }
                break;

            case "workflow_finished":
                log.info("工作流完成: workflowRunId={}, status={}",
                    event.getWorkflowRunId(), event.getData().get("status"));

                Object finalOutputs = event.getData().get("outputs");
                if (finalOutputs != null) {
                    result.setFinalOutput(finalOutputs.toString());
                    outputBuilder.append("=== 最终结果 ===\n");
                    outputBuilder.append(finalOutputs.toString()).append("\n");
                    log.info("工作流最终结果已保存: itemId={}, itemName={}", result.getItemId(), result.getItemName());
                }

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
     * 处理流式响应（从String）
     */
    public WorkflowItemResult processStreamResponse(
            String responseBody,
            Integer itemId,
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws IOException {

        return processStreamResponse(
            new BufferedReader(new StringReader(responseBody)),
            itemId, itemName, eventHandler);
    }

    /**
     * 处理流式响应（从InputStream）
     */
    public WorkflowItemResult processStreamResponse(
            InputStream inputStream,
            Integer itemId,
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws IOException {

        return processStreamResponse(
            new BufferedReader(new InputStreamReader(inputStream, "UTF-8")),
            itemId, itemName, eventHandler);
    }

    /**
     * 处理流式响应（核心实现，从Reader读取）
     */
    private WorkflowItemResult processStreamResponse(
            BufferedReader reader,
            Integer itemId,
            String itemName,
            Consumer<WorkflowEvent> eventHandler) throws IOException {

        WorkflowItemResult result = new WorkflowItemResult();
        result.setItemId(itemId);
        result.setItemName(itemName);
        result.setSuccess(true);

        StringBuilder outputBuilder = new StringBuilder();

        try (BufferedReader br = reader) {
            String line;
            while ((line = br.readLine()) != null) {
                if (line.startsWith("data: ")) {
                    String jsonData = line.substring(6);
                    if (!jsonData.trim().isEmpty() && !jsonData.equals("[DONE]")) {
                        try {
                            JsonNode eventNode = objectMapper.readTree(jsonData);
                            WorkflowEvent event = parseWorkflowEvent(eventNode);

                            if (eventHandler != null) {
                                eventHandler.accept(event);
                            }

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
     * 构建抽取任务请求体
     */
    public Map<String, Object> buildExtractionRequestBody(
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

        try {
            String requestBodyJson = objectMapper.writeValueAsString(requestBody);
            log.info("抽取任务请求体: {}", requestBodyJson);
        } catch (Exception e) {
            log.warn("输出请求体日志失败: {}", e.getMessage());
        }

        return requestBody;
    }
}
