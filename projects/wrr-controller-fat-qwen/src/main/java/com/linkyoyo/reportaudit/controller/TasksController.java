package com.linkyoyo.reportaudit.controller;

import com.linkyoyo.reportaudit.annotation.SysOperaLog;
import com.linkyoyo.reportaudit.info.TasksInfo;
import com.linkyoyo.reportaudit.query.TasksQuery;
import com.linkyoyo.reportaudit.result.R;
import com.linkyoyo.reportaudit.service.TasksService;
import com.linkyoyo.reportaudit.service.WorkflowResultService;
import com.linkyoyo.reportaudit.util.WorkflowService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.core.io.Resource;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import lombok.extern.slf4j.Slf4j;

import java.io.File;
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
            java.util.Map<String, Object> responseData = tasksService.executeCheckTask(taskId);

            if (Boolean.TRUE.equals(responseData.get("success"))) {
                return R.ok(responseData);
            } else {
                return R.error("工作流执行失败: " + responseData.get("errorMessage"));
            }

        } catch (IllegalArgumentException e) {
            log.error("执行工作流任务参数错误: taskId={}, error={}", taskId, e.getMessage());
            return R.error(e.getMessage());
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
            java.util.Map<String, Object> responseData = tasksService.executeCheckTaskBatch(taskIds, filesText);
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

            com.linkyoyo.reportaudit.entity.Tasks task;
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
            java.util.Map<String, Object> responseData = tasksService.executeEnhanceCheckTask(taskId);
            return R.ok(responseData);

        } catch (IllegalArgumentException e) {
            log.error("启动增强版工作流任务参数错误: taskId={}, error={}", taskId, e.getMessage());
            return R.error(e.getMessage());
        } catch (Exception e) {
            log.error("启动增强版工作流任务异常: taskId={}, error={}", taskId, e.getMessage(), e);
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

            String reportPath = tasksService.generateTaskReport(taskId, outputPath);

            File reportFile = new File(reportPath);
            if (!reportFile.exists()) {
                log.error("报告文件生成失败，文件不存在: {}", reportPath);
                return R.error("报告文件生成失败");
            }

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

            String reportPath = tasksService.generateTaskReport(taskId, null);

            Path filePath = Paths.get(reportPath);
            File reportFile = filePath.toFile();

            if (!reportFile.exists()) {
                log.error("报告文件不存在: {}", reportPath);
                return ResponseEntity.notFound().build();
            }

            Resource resource = new FileSystemResource(reportFile);

            String fileName = reportFile.getName();
            String encodedFileName = java.net.URLEncoder.encode(fileName, "UTF-8")
                .replaceAll("\\+", "%20");

            log.info("任务报告下载成功: taskId={}, fileName={}, size={}",
                taskId, fileName, reportFile.length());

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
}
