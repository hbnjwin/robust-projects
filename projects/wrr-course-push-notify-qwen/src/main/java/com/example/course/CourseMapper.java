package com.example.course;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface CourseMapper extends BaseMapper<CourseDO> {
    @Insert("INSERT INTO edu_course_class (course_id, class_id) VALUES (#{courseId}, #{classId})")
    void insertCourseClass(Long courseId, Long classId);
}
