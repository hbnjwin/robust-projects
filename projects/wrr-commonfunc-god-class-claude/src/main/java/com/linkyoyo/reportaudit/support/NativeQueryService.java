package com.linkyoyo.reportaudit.support;

import com.linkyoyo.reportaudit.query.CommonQueryInfo;
import lombok.extern.slf4j.Slf4j;
import org.hibernate.query.NativeQuery;
import org.hibernate.transform.Transformers;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import javax.persistence.EntityManager;
import javax.persistence.EntityManagerFactory;
import javax.persistence.Query;
import java.util.List;
import java.util.Objects;

@Service
@Slf4j
public class NativeQueryService {

    @Autowired
    private EntityManagerFactory entityManagerFactory;

    public static void clearEntityManager(EntityManager em) {
        try {
            if (Objects.nonNull(em))
                em.clear();
        } catch (Exception e) {
            log.error("clearEntityManager error:{}", e.getMessage());
        }
    }

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

    @Transactional(readOnly = true)
    public List commQuerySql(String sql) {
        EntityManager entityManager = entityManagerFactory.createEntityManager();
        Query queryNative = entityManager.createNativeQuery(sql);
        queryNative.unwrap(NativeQuery.class).setResultTransformer(Transformers.ALIAS_TO_ENTITY_MAP);
        List rows = queryNative.getResultList();
        entityManager.close();

        return rows;
    }

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
