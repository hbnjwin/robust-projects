package com.example.homework;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import org.springframework.stereotype.Service;
import java.util.List;
import java.util.Collections;

@Service
public class HomeworkService extends ServiceImpl<HomeworkMapper, HomeworkDO> {

    public List<HomeworkDO> listByClassId(Long classId) {
        return lambdaQuery().eq(HomeworkDO::getClassId, classId).list();
    }

    public void publish(HomeworkDO homework) {
        homework.setStatus(1);
        save(homework);
    }

    public void grade(Long homeworkId, Long studentId, Integer score, String comment) {
        // 保存批改结果
    }

    public List<?> getSubmissions(Long homeworkId) {
        return Collections.emptyList();
    }
}
