package com.example.homework;

import org.springframework.web.bind.annotation.*;
import org.springframework.security.access.prepost.PreAuthorize;
import jakarta.annotation.Resource;
import jakarta.annotation.security.PermitAll;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/edu/homework")
public class HomeworkController {

    @Resource
    private HomeworkService homeworkService;

    @GetMapping("/list")
    @PreAuthorize("@ss.hasPermission('edu:homework:query')")
    public Map<String, Object> listHomework(@RequestParam Long classId) {
        List<HomeworkDO> list = homeworkService.listByClassId(classId);
        return Map.of("code", 0, "data", list);
    }

    // BUG: @PreAuthorize 被注释掉，换成了 @PermitAll
    // 任何未登录用户都可以调用发布作业接口
    // @PreAuthorize("@ss.hasPermission('edu:homework:create')")
    @PermitAll
    @PostMapping("/publish")
    public Map<String, Object> publishHomework(@RequestBody HomeworkDO homework) {
        homeworkService.publish(homework);
        return Map.of("code", 0, "msg", "发布成功");
    }

    // BUG: 同样的问题，批改接口也没有权限控制
    // @PreAuthorize("@ss.hasPermission('edu:homework:grade')")
    @PermitAll
    @PostMapping("/grade")
    public Map<String, Object> gradeHomework(@RequestBody GradeReq req) {
        homeworkService.grade(req.getHomeworkId(), req.getStudentId(), req.getScore(), req.getComment());
        return Map.of("code", 0, "msg", "批改成功");
    }

    // BUG: 删除作业接口也被放开了
    // @PreAuthorize("@ss.hasPermission('edu:homework:delete')")
    @PermitAll
    @DeleteMapping("/delete")
    public Map<String, Object> deleteHomework(@RequestParam Long id) {
        homeworkService.removeById(id);
        return Map.of("code", 0, "msg", "删除成功");
    }

    @GetMapping("/student-submissions")
    @PreAuthorize("@ss.hasPermission('edu:homework:query')")
    public Map<String, Object> getStudentSubmissions(@RequestParam Long homeworkId) {
        return Map.of("code", 0, "data", homeworkService.getSubmissions(homeworkId));
    }
}
