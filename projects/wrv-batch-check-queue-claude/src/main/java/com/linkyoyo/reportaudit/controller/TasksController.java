package com.linkyoyo.reportaudit.controller;

import com.linkyoyo.reportaudit.service.TasksService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/tasks")
public class TasksController {
    @Autowired
    private TasksService tasksService;

    @GetMapping("/list")
    public Map<String, Object> list(@RequestParam(required = false) String status) {
        return tasksService.getTaskList(status);
    }

    @PostMapping("/executeCheckTask")
    public void executeCheckTask(@RequestBody Map<String, Long> body) {
        tasksService.executeCheck(body.get("taskId"));
    }
}
