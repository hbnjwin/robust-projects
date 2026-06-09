package com.example.homework;

import org.springframework.stereotype.Service;
import java.util.Map;

@Service
public class HomeworkGradeService {

    public Map<String, Object> getStudentWork(Long homeworkId, Long studentId) {
        // 查询学生提交的作业
        return Map.of(
            "homeworkId", homeworkId,
            "studentId", studentId,
            "content", "学生提交的作业内容...",
            "submittedAt", "2024-01-15 10:30:00"
        );
    }

    public void saveGrade(Long homeworkId, Long studentId, Integer score, String comment) {
        // 保存教师的批改结果到数据库
    }

    // BUG: 缺少 AI 辅助批改方法
    // 应该添加一个方法调用 AiChatModel 接口获取 AI 评语
}
