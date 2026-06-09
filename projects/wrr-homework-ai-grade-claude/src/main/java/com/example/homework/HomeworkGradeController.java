package com.example.homework;

import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import jakarta.annotation.Resource;
import java.util.Map;

@RestController
@RequestMapping("/api/edu/homework/grade")
public class HomeworkGradeController {

    @Resource
    private HomeworkGradeService gradeService;

    @GetMapping("/student-work")
    @PreAuthorize("@ss.hasPermission('edu:homework:grade')")
    public Map<String, Object> getStudentWork(@RequestParam Long homeworkId,
                                               @RequestParam Long studentId) {
        return Map.of("code", 0, "data", gradeService.getStudentWork(homeworkId, studentId));
    }

    @PostMapping("/manual")
    @PreAuthorize("@ss.hasPermission('edu:homework:grade')")
    public Map<String, Object> manualGrade(@RequestBody ManualGradeReq req) {
        gradeService.saveGrade(req.getHomeworkId(), req.getStudentId(),
                              req.getScore(), req.getComment());
        return Map.of("code", 0, "msg", "批改保存成功");
    }

    // BUG (feature gap): 缺少 AI 辅助批改接口
    // 教师需要手动逐个批改，效率太低
    // 应该增加一个 /api/edu/homework/grade/ai-assist 接口
    // 接收学生作业内容和作业要求，调用 AiChatModel 获取 AI 评语建议和建议分数
    // 教师确认或修改后再保存

    // 需要新增：
    // @PostMapping("/ai-assist")
    // public Map<String, Object> aiAssistGrade(@RequestBody AiGradeReq req) {
    //     // 1. 获取学生作业内容
    //     // 2. 获取作业要求
    //     // 3. 构建 prompt 发给 AI
    //     // 4. 返回 AI 建议的评语和分数
    // }
}
