package com.linkyoyo.reportaudit.service.impl;

import com.github.wenhao.jpa.Specifications;
import org.springframework.data.repository.CrudRepository;

import java.util.List;
import java.util.function.BiConsumer;
import java.util.function.Supplier;

/**
 * Generic utility for the delete-then-rebuild child table pattern.
 * <p>
 * Replaces duplicated child table save logic across multiple service implementations.
 * Each call performs: find existing children by FK -> delete all -> save new from Info list.
 * </p>
 *
 * <p>Usage example:</p>
 * <pre>
 * ChildTableUtils.saveChildTable(
 *     checkResultRepository,
 *     tasks.getId(),
 *     "taskId",
 *     tasksInfo.getCheckResultList(),
 *     CheckResult.builder()::build,
 *     (info, entity) -> BeanUtils.copyProperties(info, entity),
 *     (child, parentId) -> child.setTaskId(parentId)
 * );
 * </pre>
 */
public final class ChildTableUtils {

    private ChildTableUtils() {
    }

    /**
     * Deletes all existing child records matching the FK, then rebuilds from the provided items.
     *
     * @param repository     the child entity's JPA/Crud repository
     * @param parentId       the parent entity's ID value
     * @param fkFieldName    the FK field name on the child entity (e.g. "taskId", "docId")
     * @param items          list of child info objects; if null, this method is a no-op (preserves existing children)
     * @param entityFactory  creates a new empty child entity (typically ChildEntity.builder()::build)
     * @param propertyCopier copies properties from child info to child entity
     * @param fkSetter       sets the FK value on the child entity (e.g. (child, id) -> child.setTaskId(id))
     * @param <CE>           child entity type
     * @param <CI>           child info type
     * @param <ID>           parent ID type (String or Integer)
     */
    public static <CE, CI, ID> void saveChildTable(
            CrudRepository<CE, ?> repository,
            ID parentId,
            String fkFieldName,
            List<CI> items,
            Supplier<CE> entityFactory,
            BiConsumer<CI, CE> propertyCopier,
            BiConsumer<CE, ID> fkSetter) {

        if (items == null) {
            return;
        }

        // Step 1: Delete existing child records
        List<CE> existing = repository.findAll(
                Specifications.<CE>and()
                        .eq(fkFieldName, parentId)
                        .build());
        repository.deleteAll(existing);

        // Step 2: Save new child records
        for (CI item : items) {
            CE child = entityFactory.get();
            propertyCopier.accept(item, child);
            fkSetter.accept(child, parentId);
            repository.save(child);
        }
    }
}
