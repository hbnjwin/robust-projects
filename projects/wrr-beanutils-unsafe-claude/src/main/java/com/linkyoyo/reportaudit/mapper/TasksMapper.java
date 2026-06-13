package com.linkyoyo.reportaudit.mapper;

import com.linkyoyo.reportaudit.entity.Tasks;
import com.linkyoyo.reportaudit.entity.TasksCheckItems;
import com.linkyoyo.reportaudit.info.TasksCheckItemsInfo;
import com.linkyoyo.reportaudit.info.TasksInfo;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

// TODO: unmappedTargetPolicy 升级为 ERROR，待所有字段映射确认完毕后启用
@Mapper(componentModel = "spring",
        uses = {CheckResultMapper.class},
        unmappedTargetPolicy = ReportingPolicy.WARN)
public interface TasksMapper {

    // --- Tasks <-> TasksInfo ---

    TasksInfo toInfo(Tasks entity);

    Tasks toEntity(TasksInfo info);

    /**
     * 选择性更新：用于 UPDATE 分支，排除不可被客户端覆盖的字段。
     * 替代原 BeanUtils.copyProperties(info, entity, "title","status",...) 的字符串数组方式，
     * 每个 ignore 注解均在编译时验证，字段重命名会触发编译错误。
     */
    @Mapping(target = "title", ignore = true)
    @Mapping(target = "status", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    @Mapping(target = "startedAt", ignore = true)
    @Mapping(target = "completedAt", ignore = true)
    @Mapping(target = "result", ignore = true)
    @Mapping(target = "error", ignore = true)
    @Mapping(target = "creater", ignore = true)
    @Mapping(target = "deptId", ignore = true)
    @Mapping(target = "operatorCode", ignore = true)
    @Mapping(target = "progress", ignore = true)
    void updateEntitySelective(TasksInfo info, @MappingTarget Tasks entity);

    // --- TasksCheckItems <-> TasksCheckItemsInfo ---

    TasksCheckItemsInfo checkItemsToInfo(TasksCheckItems entity);

    TasksCheckItems checkItemsToEntity(TasksCheckItemsInfo info);
}
