package com.example.course;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import java.util.List;

@Mapper
public interface ClassStudentMapper {
    @Select("SELECT student_id FROM edu_class_student WHERE class_id = #{classId}")
    List<Long> getStudentIdsByClassId(Long classId);
}
