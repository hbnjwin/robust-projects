package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.info.PageInfo;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.linkyoyo.reportaudit.util.PageableUtil;
import org.springframework.beans.BeanUtils;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.transaction.annotation.Transactional;

import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import java.util.Objects;

/**
 * Abstract base class implementing the common CRUD skeleton found across all service implementations.
 * <p>
 * Uses Template Method pattern:
 * <ul>
 *   <li>{@link #createOrUpdate(Object)} is the template method</li>
 *   <li>Subclasses override hooks: {@link #beforeCreate}, {@link #beforeUpdate},
 *       {@link #saveChildTables}, {@link #copyPropertiesToEntityForUpdate}, etc.</li>
 * </ul>
 *
 * @param <E>  Entity type (e.g. Tasks, Documents, CheckResult)
 * @param <I>  Info DTO type (e.g. TasksInfo, DocumentsInfo, CheckResultInfo)
 * @param <ID> ID type (Integer or String)
 * @param <Q>  Query type (e.g. TasksQuery, DocumentsQuery)
 */
public abstract class AbstractCrudService<E, I, ID, Q> {

    @PersistenceContext
    protected EntityManager entityManager;

    // ──────────────────────────────────────────────
    // Abstract methods — subclasses MUST implement
    // ──────────────────────────────────────────────

    /**
     * @return the main JpaRepository for this service's primary entity.
     */
    protected abstract JpaRepository<E, ID> getRepository();

    /**
     * @return the ID value from the Info DTO. Used to branch create vs update.
     */
    protected abstract ID getInfoId(I info);

    /**
     * Factory for creating a new empty entity.
     * Typically: {@code EntityClass.builder()::build}
     */
    protected abstract E createEntity();

    // ──────────────────────────────────────────────
    // CREATE OR UPDATE — Template Method
    // ──────────────────────────────────────────────

    /**
     * The unified createOrUpdate skeleton. Handles:
     * <ol>
     *   <li>Create vs Update branching based on info ID being null</li>
     *   <li>Entity creation, property copying, hooks, save</li>
     *   <li>Child table saving (shared between create and update paths)</li>
     * </ol>
     * <p>
     * {@code @Transactional} ensures atomicity, especially for child table delete-then-rebuild.
     */
    @Transactional
    public E createOrUpdate(I info) {
        E entity;

        if (Objects.isNull(getInfoId(info))) {
            // ── CREATE PATH ──
            entity = createEntity();
            copyPropertiesToEntity(info, entity);
            beforeCreate(info, entity);
            entity = getRepository().save(entity);
        } else {
            // ── UPDATE PATH ──
            entityManager.clear();
            entity = getRepository().findById(getInfoId(info)).orElse(null);
            if (entity == null) {
                return null;
            }
            copyPropertiesToEntityForUpdate(info, entity);
            beforeUpdate(info, entity);
            entity = getRepository().save(entity);
        }

        // ── CHILD TABLES (shared between both paths, eliminates duplication) ──
        saveChildTables(info, entity);

        return entity;
    }

    // ──────────────────────────────────────────────
    // Template hooks — subclasses MAY override
    // ──────────────────────────────────────────────

    /**
     * Copy properties from Info to Entity during CREATE.
     * Default: {@link BeanUtils#copyProperties(Object, Object)}.
     */
    protected void copyPropertiesToEntity(I info, E entity) {
        BeanUtils.copyProperties(info, entity);
    }

    /**
     * Copy properties from Info to Entity during UPDATE.
     * Default: delegates to {@link #copyPropertiesToEntity(Object, Object)} (same as create).
     * <p>
     * Override to add ignore fields, e.g.:
     * <pre>
     * BeanUtils.copyProperties(info, entity, "title", "status", "createdAt", ...)
     * </pre>
     */
    protected void copyPropertiesToEntityForUpdate(I info, E entity) {
        copyPropertiesToEntity(info, entity);
    }

    /**
     * Hook called AFTER property copy, BEFORE save, during CREATE.
     * Use for: setting UUID, timestamps, user info, status, doc lookups, default values.
     */
    protected void beforeCreate(I info, E entity) {
        // no-op by default
    }

    /**
     * Hook called AFTER property copy, BEFORE save, during UPDATE.
     * Use for: updating timestamps, doc lookups.
     */
    protected void beforeUpdate(I info, E entity) {
        // no-op by default
    }

    /**
     * Called AFTER the main entity is saved. Handles child table delete-then-rebuild.
     * This runs for BOTH create and update paths (eliminating the duplication).
     * Use {@link ChildTableUtils#saveChildTable} for each child table.
     */
    protected void saveChildTables(I info, E entity) {
        // no-op by default
    }

    // ──────────────────────────────────────────────
    // LIST — protected helper
    // ──────────────────────────────────────────────

    /**
     * Standard list query using CommonFunc.getWhere + PageableUtil.
     * 4 of 6 services use this exact pattern.
     * The other 2 (Tasks, Documents) have custom list logic and do not call this.
     */
    protected PageInfo<E> getList(Q query) {
        Pageable pageable = PageableUtil.build(query);
        return PageableUtil.info(
                getRepository().findAll(CommonFunc.<E>getWhere(query), pageable));
    }

    // ──────────────────────────────────────────────
    // DETAIL — protected helper
    // ──────────────────────────────────────────────

    /**
     * Standard detail query: clear cache, find by ID.
     * 4 of 6 services use this exact pattern (returns entity or null).
     * The other 2 (Tasks, Documents) return enriched Info objects and override their detail methods entirely.
     */
    protected E getDetail(ID id) {
        entityManager.clear();
        return getRepository().findById(id).orElse(null);
    }
}
