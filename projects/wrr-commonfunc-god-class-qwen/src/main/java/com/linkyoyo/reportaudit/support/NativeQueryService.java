package com.linkyoyo.reportaudit.support;

import com.linkyoyo.reportaudit.query.CommonQueryInfo;
import lombok.extern.slf4j.Slf4j;
import org.hibernate.query.NativeQuery;
import org.hibernate.transform.Transformers;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import javax.persistence.EntityManager;
import javax.persistence.EntityManagerFactory;
import javax.persistence.Query;
import java.util.List;
import java.util.Objects;

/**
 * 原生 SQL 查询服务
 * 从 CommonFunc 中提取的 EntityManager 原生 SQL 执行方法
 */
@Component
@Slf4j
public class NativeQueryService {

    @Autowired
    public EntityManagerFactory entityManagerFactory;

    /**
     * 安全清除 EntityManager
     *
     * @param em EntityManager 实例
     */
    public static void clearEntityManager(EntityManager em) {
        try {
            if (Objects.nonNull(em))
                em.clear();
        } catch (Exception e) {
            log.error("clearEntityManager error:{}", e.getMessage());
        }
    }

    /**
     * 根据 CommonQueryInfo 构建并执行动态查询
     *
     * @param commonQueryInfo 查询参数（表名、字段、条件、排序）
     * @return 查询结果列表（Map 格式）
     */
    public List commQuery(CommonQueryInfo commonQueryInfo) {
        if (Objects.isNull(commonQueryInfo.getTableName()) || Objects.isNull(commonQueryInfo.getFields()))
            return null;
        Boolean haveWhere = false;
        String sql = "select " + commonQueryInfo.getFields() + " from " + commonQueryInfo.getTableName();
        if (Objects.nonNull(commonQueryInfo.getWhere()) && !commonQueryInfo.getWhere().equals("")) {
            sql = sql + " where " + commonQueryInfo.getWhere() + "=?1";
            haveWhere = true;
        }

        if (Objects.nonNull(commonQueryInfo.getSort()) && !commonQueryInfo.getSort().equals("")) {
            sql = sql + " order by " + commonQueryInfo.getSort();
        }
        EntityManager entityManager = entityManagerFactory.createEntityManager();
        Query queryNative = entityManager.createNativeQuery(sql);
        if (haveWhere)
            queryNative = queryNative.setParameter(1, commonQueryInfo.getKeyWord());

        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
        List rows = queryNative.getResultList();

        return rows;
    }

    /**
     * 直接执行 CommonQueryInfo 中的 SQL 语句
     *
     * @param commonQueryInfo 包含 SQL 的查询参数
     * @return 查询结果列表（Map 格式）
     */
    public List actQuery(CommonQueryInfo commonQueryInfo) {
        if (Objects.isNull(commonQueryInfo.getSql()))
            return null;
        String sql = commonQueryInfo.getSql();
        EntityManager entityManager = entityManagerFactory.createEntityManager();
        Query queryNative = entityManager.createNativeQuery(sql);
        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
        List rows = queryNative.getResultList();

        return rows;
    }

    /**
     * 执行任意 SQL 查询
     *
     * @param sql SQL 语句
     * @return 查询结果列表（Map 格式）
     */
    @Transactional(readOnly = true)
    public List commQuerySql(String sql) {

        EntityManager entityManager = entityManagerFactory.createEntityManager();

        Query queryNative = entityManager.createNativeQuery(sql);
        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
        List rows = queryNative.getResultList();
        entityManager.close();

        return rows;
    }

    /**
     * 调用存储过程获取模块最大值
     *
     * @param moduleName 模块名称
     * @return 最大值字符串
     */
    public String getModuleMaxValueOld(String moduleName) {
        String jpql = "CALL sp_CreateMaxValue('" + moduleName + "',@maxvalue)";
        try {
            EntityManager entityManager = entityManagerFactory.createEntityManager();
            Query querySP = entityManager.createNativeQuery(jpql);
            querySP.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
            List rw = querySP.getResultList();
            jpql = "";

            Query queryNative = entityManager.createNativeQuery("SELECT maxMainKeyValue FROM ModuleMainKey  WHERE moduleName='" + moduleName + "'");
            queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
            List<String> rows = queryNative.getResultList();
            if (rows.size() > 0) {
                jpql = rows.get(0);
            }

            return jpql;
        } catch (Exception e) {
            log.info("获取最大值错误：" + e.getMessage());
            return "";
        }
    }
}
