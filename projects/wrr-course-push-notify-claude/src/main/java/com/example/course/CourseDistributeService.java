package com.example.course;

import org.springframework.stereotype.Service;
import jakarta.annotation.Resource;
import java.util.List;

@Service
public class CourseDistributeService {

    @Resource
    private CourseMapper courseMapper;

    @Resource
    private ClassStudentMapper classStudentMapper;

    // BUG (feature gap): 课程分发后没有给学生发通知
    // 学生只有手动刷新才能看到新课程
    // 应该接入 NotifyTemplate 模块自动发站内通知
    public void distributeCourse(Long courseId, List<Long> classIds) {
        CourseDO course = courseMapper.selectById(courseId);
        if (course == null) {
            throw new RuntimeException("课程不存在");
        }

        for (Long classId : classIds) {
            // 创建课程-班级关联
            courseMapper.insertCourseClass(courseId, classId);

            // BUG: 分发完成但没有通知学生
            // 应该在这里获取班级的所有学生，然后发送站内通知
            // List<Long> studentIds = classStudentMapper.getStudentIdsByClassId(classId);
            // notifyService.sendBatch(studentIds, "新课程通知",
            //     "您的班级新增了课程：" + course.getName() + "，点击查看");
        }

        course.setDistributed(true);
        courseMapper.updateById(course);
    }
}
