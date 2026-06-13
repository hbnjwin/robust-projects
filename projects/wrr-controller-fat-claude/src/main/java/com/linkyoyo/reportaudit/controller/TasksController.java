package com.linkyoyo.reportaudit.controller;

import com.linkyoyo.reportaudit.annotation.SysOperaLog;
import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.info.TasksInfo;
import com.linkyoyo.reportaudit.query.TasksQuery;
import com.linkyoyo.reportaudit.result.R;
import com.linkyoyo.reportaudit.service.TasksService;
import com.linkyoyo.reportaudit.util.WorkflowService;
import com.linkyoyo.reportaudit.util.WorkflowResult;
import com.linkyoyo.reportaudit.util.WorkflowItemResult;
import com.linkyoyo.reportaudit.util.WorkflowEvent;
import com.linkyoyo.reportaudit.util.EnhancedWorkflowProcessor;
import com.linkyoyo.reportaudit.service.WorkflowResultService;
import com.linkyoyo.reportaudit.service.TaskProgressNotificationService;
import com.querydsl.jpa.impl.JPAQueryFactory;
import static com.linkyoyo.reportaudit.entity.QTasks.tasks;
import static com.linkyoyo.reportaudit.entity.QDocuments.documents;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.core.io.Resource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import lombok.extern.slf4j.Slf4j;

import java.util.function.Consumer;
import java.util.concurrent.CompletableFuture;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@RequestMapping("/tasks")
@RestController
@Slf4j
public class TasksController {
    @Autowired
    private TasksService tasksService;
    
    @Autowired
    private WorkflowService workflowService;
    
    @Autowired
    private WorkflowResultService workflowResultService;
    
    @Autowired
    private EnhancedWorkflowProcessor enhancedWorkflowProcessor;
    
    @Autowired
    private JPAQueryFactory queryFactory;
    
    @Autowired
    private TaskProgressNotificationService taskProgressNotificationService;

    @GetMapping("/list")
    public R getTasksList(TasksQuery tasksQuery) {
        return R.ok(tasksService.getTasksList(tasksQuery));
    }

    @GetMapping("/listDetail")
    public R getTasksDetail(TasksInfo tasksInfo) {
        return R.ok(tasksService.getTasksDetail(tasksInfo.getId()));
    }

    @PostMapping("/update")
    @SysOperaLog(value="创建/更新任务",id="检查任务")
    public R updateData(@RequestBody TasksInfo tasksInfo) {
        return R.ok(tasksService.createOrUpdate(tasksInfo));
    }

    @RequestMapping("/delete")
    public R delete(@RequestParam("id") String id) {
        if (id == null || id.trim().isEmpty()) {
            return R.warning("id不能为空");
        }
        tasksService.markDeleted(id);
        return R.ok("删除成功");
    }

    /**
     * 执行工作流检查任务
     * @param taskId 任务ID
     * @return 执行结果
     */
    @PostMapping("/executeCheckTask")
    public R executeCheckTask(@RequestParam String taskId) {
        try {
            log.info("开始执行工作流检查任务: taskId={}", taskId);
            
            // 发送任务开始通知
            taskProgressNotificationService.notifyTaskStarted(taskId, "check");
            
            // 通过QueryDSL查询任务信息获取originalDocId
            Tasks task = queryFactory
                .selectFrom(tasks)
                .where(tasks.id.eq(taskId))
                .fetchOne();
            
            if (task == null) {
                log.error("未找到检查任务: taskId={}", taskId);
                return R.error("未找到指定的检查任务");
            }
            
            if (task.getOriginalDocId() == null) {
                log.error("检查任务缺少原始文档ID: taskId={}", taskId);
                return R.error("检查任务缺少原始文档ID");
            }
            
            // 通过QueryDSL查询Documents表获取mdContent
            Documents document = queryFactory
                .selectFrom(documents)
                .where(documents.id.eq(task.getOriginalDocId().intValue()))
                .fetchOne();
            
            if (document == null) {
                log.error("未找到原始文档: docId={}", task.getOriginalDocId());
                return R.error("未找到原始文档");
            }
            
            String filesText = document.getMdContent();
            if (filesText == null || filesText.trim().isEmpty()) {
                log.error("原始文档内容为空: docId={}", task.getOriginalDocId());
                return R.error("原始文档内容为空");
            }
            
            log.info("获取到文档内容: taskId={}, docId={}, contentLength={}", 
                taskId, task.getOriginalDocId(), filesText.length());
            
            // 创建事件处理器来收集工作流事件
            StringBuilder eventLog = new StringBuilder();
            Consumer<WorkflowEvent> eventHandler = event -> {
                String eventInfo = String.format("[%s] %s - %s", 
                    event.getEvent(), event.getWorkflowRunId(), event.getData());
                eventLog.append(eventInfo).append("\n");
                log.info("工作流事件: {}", eventInfo);
            };

            
            // 同步执行工作流任务
            WorkflowResult result = workflowService.executeCheckTaskSync(
                taskId, filesText, eventHandler);
            
            // 🔥 关键：工作流执行完成后的结果处理和入库操作
            log.info("工作流执行完成，开始处理结果入库: taskId={}", taskId);
            java.util.Map<String, Object> processResult = workflowResultService.processWorkflowResult(result, filesText);
            
            // 构建响应数据
            java.util.Map<String, Object> responseData = new java.util.HashMap<>();
            responseData.put("taskId", result.getTaskId());
            responseData.put("taskType", result.getTaskType());
            responseData.put("success", result.isSuccess());
            responseData.put("errorMessage", result.getErrorMessage());
            responseData.put("itemResults", result.getItemResults());
            responseData.put("eventLog", eventLog.toString());
            
            // 添加入库处理结果
            responseData.put("processResult", processResult);
            responseData.put("processSuccess", processResult.get("success"));
            responseData.put("processMessage", processResult.get("message"));
            
            if (result.isSuccess()) {
                log.info("工作流任务执行成功: taskId={}, itemCount={}, processSuccess={}", 
                    taskId, result.getItemResults() != null ? result.getItemResults().size() : 0,
                    processResult.get("success"));
                
                // 发送任务完成通知
                taskProgressNotificationService.notifyTaskCompleted(taskId, "check", true);
                return R.ok(responseData);
            } else {
                log.error("工作流任务执行失败: taskId={}, error={}", taskId, result.getErrorMessage());
                
                // 发送任务失败通知
                taskProgressNotificationService.notifyTaskError(taskId, "check", result.getErrorMessage());
                return R.error("工作流执行失败: " + result.getErrorMessage());
            }
            
        } catch (Exception e) {
            log.error("执行工作流任务异常: taskId={}, error={}", taskId, e.getMessage(), e);
            return R.error("执行工作流任务异常: " + e.getMessage());
        }
    }

    /**
     * 批量执行工作流检查任务
     * @param taskIds 任务ID数组
     * @param filesText 文档内容
     * @return 批量执行结果
     */
    @PostMapping("/executeCheckTaskBatch")
    public R executeCheckTaskBatch(@RequestParam String[] taskIds, @RequestParam String filesText) {
        try {
            log.info("开始批量执行工作流检查任务: count={}", taskIds.length);
            
            // 创建事件处理器
            java.util.List<String> eventLogs = new java.util.ArrayList<>();
            Consumer<WorkflowEvent> eventHandler = event -> {
                String eventInfo = String.format("[%s] TaskId:%s WorkflowRunId:%s - %s", 
                    event.getEvent(), event.getTaskId(), event.getWorkflowRunId(), event.getData());
                eventLogs.add(eventInfo);
                log.info("批量工作流事件: {}", eventInfo);
            };
            
            // 同步批量执行
            WorkflowResult[] results = workflowService.executeCheckTasksBatchSync(
                taskIds, filesText, eventHandler);
            
            // 🔥 关键：批量工作流执行完成后的结果处理和入库操作
            log.info("批量工作流执行完成，开始处理结果入库: count={}", results.length);
            
            // 处理每个工作流结果（新格式）
            int successProcessCount = 0;
            int errorProcessCount = 0;
            for (WorkflowResult result : results) {
                try {
                    // 将WorkflowResult转换为JSON字符串格式处理
                    String workflowResultJson = convertWorkflowResultToJson(result);
                    
                    java.util.Map<String, Object> processResult;
                    if ("extraction".equals(result.getTaskType())) {
                        processResult = workflowResultService.processExtractionWorkflowResult(workflowResultJson);
                    } else {
                        processResult = workflowResultService.processCheckWorkflowResult(workflowResultJson);
                    }
                    
                    if ((Boolean) processResult.get("success")) {
                        successProcessCount++;
                    } else {
                        errorProcessCount++;
                        log.warn("工作流结果处理失败: taskId={}, message={}", 
                            result.getTaskId(), processResult.get("message"));
                    }
                } catch (Exception e) {
                    errorProcessCount++;
                    log.error("处理工作流结果异常: taskId={}, error={}", result.getTaskId(), e.getMessage(), e);
                }
            }
            
            java.util.Map<String, Object> batchProcessResult = new java.util.HashMap<>();
            batchProcessResult.put("success", errorProcessCount == 0);
            batchProcessResult.put("savedItemCount", successProcessCount);
            batchProcessResult.put("errorItemCount", errorProcessCount);
            batchProcessResult.put("message", String.format("批量处理完成，成功%d项，失败%d项", successProcessCount, errorProcessCount));
            
            // 统计结果
            int successCount = 0;
            int failureCount = 0;
            java.util.List<java.util.Map<String, Object>> resultList = new java.util.ArrayList<>();
            
            for (WorkflowResult result : results) {
                java.util.Map<String, Object> resultData = new java.util.HashMap<>();
                resultData.put("taskId", result.getTaskId());
                resultData.put("taskType", result.getTaskType());
                resultData.put("success", result.isSuccess());
                resultData.put("errorMessage", result.getErrorMessage());
                resultData.put("itemResults", result.getItemResults());
                
                if (result.isSuccess()) {
                    successCount++;
                } else {
                    failureCount++;
                }
                
                resultList.add(resultData);
            }
            
            // 构建响应数据
            java.util.Map<String, Object> responseData = new java.util.HashMap<>();
            responseData.put("totalCount", results.length);
            responseData.put("successCount", successCount);
            responseData.put("failureCount", failureCount);
            responseData.put("results", resultList);
            responseData.put("eventLogs", eventLogs);
            
            // 添加批量入库处理结果
            responseData.put("batchProcessResult", batchProcessResult);
            responseData.put("processSuccess", batchProcessResult.get("success"));
            responseData.put("processMessage", batchProcessResult.get("message"));
            responseData.put("savedItemCount", batchProcessResult.get("savedItemCount"));
            responseData.put("errorItemCount", batchProcessResult.get("errorItemCount"));
            
            log.info("批量工作流任务执行完成: total={}, success={}, failure={}, processSuccess={}", 
                results.length, successCount, failureCount, batchProcessResult.get("success"));
            
            return R.ok(responseData);
            
        } catch (Exception e) {
            log.error("批量执行工作流任务异常: error={}", e.getMessage(), e);
            return R.error("批量执行工作流任务异常: " + e.getMessage());
        }
    }

    /**
     * 查询任务信息（带缓存策略）
     * @param taskId 任务ID
     * @param forceRefresh 是否强制刷新缓存
     * @return 任务信息
     */
    @GetMapping("/queryTask")
    public R queryTask(@RequestParam String taskId, 
                      @RequestParam(defaultValue = "false") boolean forceRefresh) {
        try {
            log.info("查询检查任务: taskId={}, forceRefresh={}", taskId, forceRefresh);
            
            Tasks task;
            if (forceRefresh) {
                task = workflowService.queryCheckTaskById(taskId, 
                    com.linkyoyo.reportaudit.util.EntityManagerCacheHelper.CacheStrategy.CLEAR_CACHE);
            } else {
                task = workflowService.queryCheckTaskById(taskId);
            }
            
            if (task != null) {
                log.info("查询到任务: taskId={}, title={}, status={}", 
                    taskId, task.getTitle(), task.getStatus());
                return R.ok(task);
            } else {
                log.warn("未找到任务: taskId={}", taskId);
                return R.error("未找到指定的任务");
            }
            
        } catch (Exception e) {
            log.error("查询任务异常: taskId={}, error={}", taskId, e.getMessage(), e);
            return R.error("查询任务异常: " + e.getMessage());
        }
    }

    /**
     * 查询工作流执行历史
     * @param taskId 任务ID
     * @param taskType 任务类型（extraction/check）
     * @return 执行历史
     */
    @GetMapping("/workflowHistory")
    public R getWorkflowHistory(@RequestParam String taskId, 
                               @RequestParam(defaultValue = "check") String taskType) {
        try {
            log.info("查询工作流执行历史: taskId={}, taskType={}", taskId, taskType);
            
            java.util.Map<String, Object> history = workflowResultService.getWorkflowHistory(taskId, taskType);
            
            if ((Boolean) history.get("success")) {
                return R.ok(history);
            } else {
                return R.error((String) history.get("message"));
            }
            
        } catch (Exception e) {
            log.error("查询工作流历史异常: taskId={}, taskType={}, error={}", 
                taskId, taskType, e.getMessage(), e);
            return R.error("查询工作流历史异常: " + e.getMessage());
        }
    }

    /**
     * 执行增强版工作流检查任务（异步）
     * 支持根据检查项的关联配置动态获取文档内容
     * 任务开始后立即返回，通过WebSocket通知执行进度
     * @param taskId 任务ID
     * @return 执行结果
     */
    @RequestMapping("/executeEnhanceCheckTask")
    @SysOperaLog(value="执行任务",id="检查任务")
    public R executeEnhanceCheckTask(@RequestParam String taskId) {
        try {
            log.info("开始执行增强版工作流检查任务（异步）: taskId={}", taskId);
            
            // 发送任务开始通知
            // 这里先不发送开始通知，等任务验证通过后再发送
            
            // 通过QueryDSL查询任务信息
            Tasks task = queryFactory
                .selectFrom(tasks)
                .where(tasks.id.eq(taskId))
                .fetchOne();
            
            if (task == null) {
                log.error("未找到检查任务: taskId={}", taskId);
                taskProgressNotificationService.notifyTaskError(taskId, "check", "未找到指定的检查任务");
                return R.error("未找到指定的检查任务");
            }
            
            if (task.getOriginalDocId() == null) {
                log.error("检查任务缺少原始文档ID: taskId={}", taskId);
                taskProgressNotificationService.notifyTaskError(taskId, "check", "检查任务缺少原始文档ID");
                return R.error("检查任务缺少原始文档ID");
            }
            
            log.info("获取到任务信息: taskId={}, originalDocId={}, selectedItems={}", 
                taskId, task.getOriginalDocId(), task.getSelectedItems());
            
            // 发送任务开始通知
            taskProgressNotificationService.notifyTaskStarted(taskId, "check");
            
            // 异步执行任务 - 使用新的异步服务方法
            enhancedWorkflowProcessor.executeEnhanceCheckTaskAsync(task, taskId, taskProgressNotificationService);
            
            // 立即返回任务已开始的响应
            java.util.Map<String, Object> responseData = new java.util.HashMap<>();
            responseData.put("taskId", taskId);
            responseData.put("taskType", "enhance_check");
            responseData.put("status", "started");
            responseData.put("message", "检查任务已开始执行，请通过WebSocket监听执行进度");
            
            return R.ok(responseData);
            
        } catch (Exception e) {
            log.error("启动增强版工作流任务异常: taskId={}, error={}", taskId, e.getMessage(), e);
            taskProgressNotificationService.notifyTaskError(taskId, "enhance_check", "启动任务异常: " + e.getMessage());
            return R.error("启动增强版工作流任务异常: " + e.getMessage());
        }
    }

    /**
     * 生成任务检查报告
     * 生成 Word 格式的任务检查报告并返回文件路径
     * 
     * @param taskId 任务ID
     * @param outputPath 输出路径（可选，为空时使用默认路径）
     * @return 生成的报告文件路径
     */
    @GetMapping("/generateReport")
    @SysOperaLog(value="生成任务报告", id="检查任务")
    public R generateTaskReport(@RequestParam String taskId, 
                               @RequestParam(required = false) String outputPath) {
        try {
            log.info("开始生成任务检查报告: taskId={}, outputPath={}", taskId, outputPath);
            
            // 调用 Service 生成报告
            String reportPath = tasksService.generateTaskReport(taskId, outputPath);
            
            // 检查文件是否存在
            File reportFile = new File(reportPath);
            if (!reportFile.exists()) {
                log.error("报告文件生成失败，文件不存在: {}", reportPath);
                return R.error("报告文件生成失败");
            }
            
            // 构建响应数据
            java.util.Map<String, Object> responseData = new java.util.HashMap<>();
            responseData.put("taskId", taskId);
            responseData.put("reportPath", reportPath);
            responseData.put("fileName", reportFile.getName());
            responseData.put("fileSize", reportFile.length());
            responseData.put("message", "报告生成成功");
            
            log.info("任务报告生成成功: taskId={}, reportPath={}, size={}", 
                taskId, reportPath, reportFile.length());
            
            return R.ok(responseData);
            
        } catch (IllegalArgumentException e) {
            log.error("生成任务报告失败，参数错误: taskId={}, error={}", taskId, e.getMessage());
            return R.error(e.getMessage());
        } catch (Exception e) {
            log.error("生成任务报告异常: taskId={}, error={}", taskId, e.getMessage(), e);
            return R.error("生成任务报告异常: " + e.getMessage());
        }
    }
    
    /**
     * 下载任务检查报告
     * 生成并直接下载 Word 格式的任务检查报告
     * 
     * @param taskId 任务ID
     * @return 报告文件下载
     */
    @GetMapping("/downloadReport")
    @SysOperaLog(value="下载任务报告", id="检查任务")
    public ResponseEntity<Resource> downloadTaskReport(@RequestParam String taskId) {
        try {
            log.info("开始下载任务检查报告: taskId={}", taskId);
            
            // 生成报告
            String reportPath = tasksService.generateTaskReport(taskId, null);
            
            // 读取文件
            Path filePath = Paths.get(reportPath);
            File reportFile = filePath.toFile();
            
            if (!reportFile.exists()) {
                log.error("报告文件不存在: {}", reportPath);
                return ResponseEntity.notFound().build();
            }
            
            // 构建文件资源
            Resource resource = new FileSystemResource(reportFile);
            
            // 获取文件名（支持中文）
            String fileName = reportFile.getName();
            String encodedFileName = java.net.URLEncoder.encode(fileName, "UTF-8")
                .replaceAll("\\+", "%20");
            
            log.info("任务报告下载成功: taskId={}, fileName={}, size={}", 
                taskId, fileName, reportFile.length());
            
            // 返回文件下载响应
            return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType("application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                .header(HttpHeaders.CONTENT_DISPOSITION, 
                    "attachment; filename=\"" + encodedFileName + "\"; filename*=UTF-8''" + encodedFileName)
                .header(HttpHeaders.CONTENT_LENGTH, String.valueOf(reportFile.length()))
                .body(resource);
                
        } catch (IllegalArgumentException e) {
            log.error("下载任务报告失败，参数错误: taskId={}, error={}", taskId, e.getMessage());
            return ResponseEntity.badRequest().build();
        } catch (Exception e) {
            log.error("下载任务报告异常: taskId={}, error={}", taskId, e.getMessage(), e);
            return ResponseEntity.status(500).build();
        }
    }

    /**
     * 将WorkflowResult转换为新格式的JSON字符串
     * 用于兼容新的工作流结果处理逻辑
     */
    private String convertWorkflowResultToJson(WorkflowResult result) {
        try {
            // 构建符合新格式的JSON结构
            java.util.Map<String, Object> workflowResult = new java.util.HashMap<>();
            workflowResult.put("event", "workflow_finished");
            workflowResult.put("workflow_run_id", java.util.UUID.randomUUID().toString());
            workflowResult.put("task_id", result.getTaskId());
            
            java.util.Map<String, Object> data = new java.util.HashMap<>();
            data.put("id", java.util.UUID.randomUUID().toString());
            data.put("workflow_id", java.util.UUID.randomUUID().toString());
            data.put("sequence_number", 1);
            data.put("status", result.isSuccess() ? "succeeded" : "failed");
            
            // 构建outputs节点
            java.util.Map<String, Object> outputs = new java.util.HashMap<>();
            if (result.getItemResults() != null && !result.getItemResults().isEmpty()) {
                WorkflowItemResult firstItem = result.getItemResults().get(0);
                outputs.put("text", firstItem.getOutput());
                outputs.put("taskId", result.getTaskId());
                outputs.put("documentId", "1"); // 默认文档ID
                outputs.put("checkId", firstItem.getItemId());
                outputs.put("checkName", firstItem.getItemName());
            } else {
                outputs.put("text", result.getErrorMessage());
                outputs.put("taskId", result.getTaskId());
                outputs.put("documentId", "1");
                outputs.put("checkId", "1");
                outputs.put("checkName", "未知");
            }
            
            data.put("outputs", outputs);
            data.put("error", result.isSuccess() ? null : result.getErrorMessage());
            data.put("created_at", System.currentTimeMillis() / 1000);
            data.put("finished_at", System.currentTimeMillis() / 1000);
            
            workflowResult.put("data", data);
            
            // 转换为JSON字符串
            com.fasterxml.jackson.databind.ObjectMapper mapper = new com.fasterxml.jackson.databind.ObjectMapper();
            return mapper.writeValueAsString(workflowResult);
            
        } catch (Exception e) {
            log.error("转换WorkflowResult为JSON失败: taskId={}, error={}", result.getTaskId(), e.getMessage(), e);
            return "{}";
        }
    }
}
