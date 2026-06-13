package com.linkyoyo.reportaudit.service.impl;

import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.jpa.repository.JpaRepository;

import javax.persistence.EntityManager;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * CRUD 服务通用基类，封装 createOrUpdate 的模板方法。
 *
 * @param <E>  实体类型
 * @param <I>  Info（DTO）类型
 * @param <ID> 主键类型
 */
public abstract class AbstractCrudServiceImpl<E, I, ID> {

    @Autowired
    protected EntityManager entityManager;

    /** 返回主实体的 Repository */
    protected abstract JpaRepository<E, ID> getRepository();

    /** 创建空实体实例，例如 Entity.builder().build() */
    protected abstract E newEntity();

    /** 从 Info 对象获取主键 */
    protected abstract ID getInfoId(I info);

    /** 新增前的钩子（UUID 生成、时间戳、用户信息等） */
    protected void beforeCreate(E entity, I info) {}

    /** 修改前的钩子 */
    protected void beforeUpdate(E entity, I info) {}

    /** 修改时 BeanUtils.copyProperties 需要排除的属性 */
    protected String[] getUpdateExcludeProperties() {
        return new String[0];
    }

    /** 返回子表处理器列表（按声明顺序执行） */
    protected List<ChildTableHandler<E, I, ?, ?>> getChildTableHandlers() {
        return Collections.emptyList();
    }

    /**
     * 通用的新增或修改逻辑。
     * <ul>
     *   <li>id 为空 → 新增：copyProperties → beforeCreate → save → saveChildren</li>
     *   <li>id 非空 → 修改：clear → findById → copyProperties（可排除字段） → beforeUpdate → save → saveChildren</li>
     * </ul>
     */
    public E createOrUpdate(I info) {
        if (Objects.isNull(getInfoId(info))) {
            E entity = newEntity();
            BeanUtils.copyProperties(info, entity);
            beforeCreate(entity, info);
            entity = getRepository().save(entity);
            saveChildren(entity, info);
            return entity;
        } else {
            entityManager.clear();
            E entity = getRepository().findById(getInfoId(info)).orElse(null);
            if (entity != null) {
                String[] excludes = getUpdateExcludeProperties();
                if (excludes.length > 0) {
                    BeanUtils.copyProperties(info, entity, excludes);
                } else {
                    BeanUtils.copyProperties(info, entity);
                }
                beforeUpdate(entity, info);
                entity = getRepository().save(entity);
                saveChildren(entity, info);
            }
            return entity;
        }
    }

    private void saveChildren(E entity, I info) {
        for (ChildTableHandler<E, I, ?, ?> handler : getChildTableHandlers()) {
            handler.saveChildren(entity, info);
        }
    }
}
