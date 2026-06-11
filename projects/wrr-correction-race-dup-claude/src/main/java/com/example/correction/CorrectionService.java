package com.example.correction;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import org.springframework.stereotype.Service;
import jakarta.annotation.Resource;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class CorrectionService {

    @Resource
    private CorrectionMapper correctionMapper;

    @Resource
    private PaperCorrectionTaskMapper taskMapper;

    public Long startCorrection(Long classId, Long homeworkId, Long teacherId) {
        // BUG: 没有幂等检查，不检查是否已有进行中的批改记录
        // 两个老师同时点击"开始批改"会创建两条 correction 记录
        CorrectionDO correction = new CorrectionDO();
        correction.setClassId(classId);
        correction.setHomeworkId(homeworkId);
        correction.setTeacherId(teacherId);
        correction.setStatus("running");
        correction.setCreateTime(LocalDateTime.now());
        correctionMapper.insert(correction);

        // BUG: 创建批改子任务时也没有检查是否已存在
        // 导致同一个学生的作业被创建了两个批改任务
        List<Long> studentIds = getStudentIds(classId);
        for (Long studentId : studentIds) {
            PaperCorrectionTaskDO task = new PaperCorrectionTaskDO();
            task.setCorrectionId(correction.getId());
            task.setStudentId(studentId);
            task.setStatus("pending");
            taskMapper.insert(task);  // BUG: 可能重复插入
        }

        // BUG: 没有使用分布式锁来防止并发
        // 应该用 Redis 分布式锁: classId + homeworkId 作为锁 key

        return correction.getId();
    }

    public CorrectionProgressVO getProgress(Long homeworkId) {
        CorrectionDO correction = correctionMapper.selectOne(
            new LambdaQueryWrapper<CorrectionDO>()
                .eq(CorrectionDO::getHomeworkId, homeworkId)
                .eq(CorrectionDO::getStatus, "running")
                .last("LIMIT 1")
        );
        if (correction == null) return null;

        long total = taskMapper.selectCount(
            new LambdaQueryWrapper<PaperCorrectionTaskDO>()
                .eq(PaperCorrectionTaskDO::getCorrectionId, correction.getId())
        );
        long corrected = taskMapper.selectCount(
            new LambdaQueryWrapper<PaperCorrectionTaskDO>()
                .eq(PaperCorrectionTaskDO::getCorrectionId, correction.getId())
                .eq(PaperCorrectionTaskDO::getStatus, "completed")
        );

        CorrectionProgressVO vo = new CorrectionProgressVO();
        vo.setTotal((int) total);
        vo.setCorrected((int) corrected);
        vo.setStatus(corrected >= total ? "completed" : "running");
        return vo;
    }

    private List<Long> getStudentIds(Long classId) {
        return List.of(1L, 2L, 3L); // 简化：实际从班级表查询
    }
}
