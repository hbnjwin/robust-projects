package com.linkyoyo.reportaudit.service;

import com.linkyoyo.reportaudit.entity.ExtractionTasks;
import java.util.List;

public interface ExtractionTasksService {
    ExtractionTasks createTask(List<Long> documentIds, Long configId);
    void executeTask(Long taskId);
    ExtractionTasks getTask(Long taskId);
}
