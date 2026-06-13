package com.linkyoyo.reportaudit.service.impl;

import com.github.wenhao.jpa.Specifications;
import org.springframework.beans.BeanUtils;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;

import java.util.List;
import java.util.function.BiConsumer;
import java.util.function.Function;
import java.util.function.Supplier;

/**
 * 封装子表"先删后建"的通用逻辑。
 *
 * @param <E>  父实体类型
 * @param <I>  父 Info（DTO）类型
 * @param <CE> 子实体类型
 * @param <CI> 子 Info（DTO）类型
 */
public class ChildTableHandler<E, I, CE, CI> {

    private final JpaRepository<CE, ?> childRepository;
    private final String fkFieldName;
    private final Function<I, List<CI>> childListGetter;
    private final Supplier<CE> childEntityFactory;
    private final BiConsumer<CE, E> fkSetter;
    private final Function<E, Object> parentIdGetter;

    public ChildTableHandler(JpaRepository<CE, ?> childRepository,
                             String fkFieldName,
                             Function<I, List<CI>> childListGetter,
                             Supplier<CE> childEntityFactory,
                             BiConsumer<CE, E> fkSetter,
                             Function<E, Object> parentIdGetter) {
        this.childRepository = childRepository;
        this.fkFieldName = fkFieldName;
        this.childListGetter = childListGetter;
        this.childEntityFactory = childEntityFactory;
        this.fkSetter = fkSetter;
        this.parentIdGetter = parentIdGetter;
    }

    @SuppressWarnings("unchecked")
    public void saveChildren(E parentEntity, I parentInfo) {
        List<CI> childInfoList = childListGetter.apply(parentInfo);
        if (childInfoList == null) {
            return;
        }

        Object parentId = parentIdGetter.apply(parentEntity);
        JpaSpecificationExecutor<CE> specExecutor = (JpaSpecificationExecutor<CE>) childRepository;

        Specification<CE> spec = Specifications.<CE>and()
                .eq(fkFieldName, parentId)
                .build();
        List<CE> existing = specExecutor.findAll(spec);
        childRepository.deleteAll(existing);

        for (CI childInfo : childInfoList) {
            CE childEntity = childEntityFactory.get();
            BeanUtils.copyProperties(childInfo, childEntity);
            fkSetter.accept(childEntity, parentEntity);
            childRepository.save(childEntity);
        }
    }

    public static <E, I, CE, CI> ChildTableHandler<E, I, CE, CI> of(
            JpaRepository<CE, ?> childRepository,
            String fkFieldName,
            Function<I, List<CI>> childListGetter,
            Supplier<CE> childEntityFactory,
            BiConsumer<CE, E> fkSetter,
            Function<E, Object> parentIdGetter) {
        return new ChildTableHandler<>(childRepository, fkFieldName, childListGetter,
                childEntityFactory, fkSetter, parentIdGetter);
    }
}
