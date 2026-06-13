package com.linkyoyo.reportaudit.service;

import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.info.TasksInfo;
import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.query.TasksQuery;

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
}
