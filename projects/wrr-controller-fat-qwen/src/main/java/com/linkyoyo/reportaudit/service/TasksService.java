package com.linkyoyo.reportaudit.service;

import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.info.TasksInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.TasksQuery;

import java.util.Map;

public interface TasksService {

    PageInfo<TasksInfo> getTasksList(TasksQuery tasksQuery);

    Tasks createOrUpdate(TasksInfo tasksInfo);

    TasksInfo getTasksDetail(String id);

    /**
     * 生成任务检查报告
     *
     * @param taskId 任务ID
     * @param outputPath 输出文件路径（可选，为null时使用默认路径）
     * @return 生成的报告文件路径
     * @throws Exception 生成失败时抛出异常
     */
    String generateTaskReport(String taskId, String outputPath) throws Exception;

    void markDeleted(String id);

    /**
     * 执行工作流检查任务
     * 包含：查询任务和文档、构建事件处理器、调用工作流、处理结果入库
     *
     * @param taskId 任务ID
     * @return 执行结果（包含工作流结果和入库处理结果）
     * @throws Exception 执行失败时抛出异常
     */
    Map<String, Object> executeCheckTask(String taskId) throws Exception;

    /**
     * 批量执行工作流检查任务
     * 包含：构建事件处理器、批量调用工作流、处理每个结果入库、汇总统计
     *
     * @param taskIds 任务ID数组
     * @param filesText 文档内容
     * @return 批量执行结果（包含统计和每个任务的结果）
     * @throws Exception 执行失败时抛出异常
     */
    Map<String, Object> executeCheckTaskBatch(String[] taskIds, String filesText) throws Exception;

    /**
     * 执行增强版工作流检查任务（异步）
     * 包含：查询任务信息、启动异步执行
     *
     * @param taskId 任务ID
     * @return 启动响应（任务已开始执行）
     * @throws Exception 启动失败时抛出异常
     */
    Map<String, Object> executeEnhanceCheckTask(String taskId) throws Exception;
}
