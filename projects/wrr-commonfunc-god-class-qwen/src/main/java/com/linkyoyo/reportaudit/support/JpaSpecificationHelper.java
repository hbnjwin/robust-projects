package com.linkyoyo.reportaudit.support;

import cn.hutool.core.util.StrUtil;
import com.github.wenhao.jpa.PredicateBuilder;
import com.github.wenhao.jpa.Specifications;
import org.springframework.data.jpa.domain.Specification;

import java.lang.reflect.Field;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;

/**
 * JPA Specification 动态条件构建工具类
 * 从 CommonFunc 中提取的 JPA 动态查询条件构建方法
 */
public class JpaSpecificationHelper {

    /**
     * 根据逗号分隔的字段列表和关键字构建 JPA Specification
     *
     * @param strWhere    逗号分隔的字段名列表
     * @param keyWord     搜索关键字
     * @param haveDelFlag 是否包含软删除标志过滤
     * @param <T>         实体类型
     * @return JPA Specification 对象
     */
    public static <T> Specification<T> getWhere(String strWhere, String keyWord, Boolean haveDelFlag) {
        PredicateBuilder<T> specEmp = Specifications.<T>or();
        PredicateBuilder<T> specFlag = Specifications.<T>and();
        if (haveDelFlag) {
            if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
                specFlag.eq("delFlag", false);
                return specFlag.build();

            }
        }

        if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
            return specEmp.build();
        }
        if (Objects.isNull(strWhere) || strWhere.trim().equals("")) {
            return specEmp.build();
        }
        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        for (String s : lstWhere) {

            if (s.equals("id") || StrUtil.subSufByLength(s, 2).equals("Id") || StrUtil.subSufByLength(s, 5).equals("Level"))
                specEmp.eq(s, keyWord);
            else
                specEmp.like(s, "%" + keyWord + "%");

        }
        if (haveDelFlag) {
            specFlag.eq("delFlag", false);
            return specFlag.predicate(specEmp.build()).build();

        } else {
            return specEmp.build();
        }
    }

    /**
     * 根据 Query 对象构建 JPA Specification
     * 通过反射检查实体字段类型，自动选择 eq 或 like 匹配方式
     *
     * @param query Query 对象（包含 where、keyWord 等条件）
     * @param <T>   实体类型
     * @return JPA Specification 对象
     */
    public static <T> Specification<T> getWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        String strWhere = query.getWhere();
        String keyWord = query.getKeyWord();
        boolean haveDelFlag = false;
        Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
        Class clazz = (Class) params[0];
        // 判断是否含有delFlag字段
        Field field = Arrays.asList(clazz.getDeclaredFields())
                .stream().filter(f -> f.getName().toLowerCase().equals("delflag".toLowerCase())).findFirst().orElse(null);
        if (field != null)
            haveDelFlag = true;

        PredicateBuilder<T> specEmp = Specifications.<T>or();
        PredicateBuilder<T> specFlag = Specifications.<T>and();
        if (haveDelFlag) {
            if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
                specFlag.ne("delFlag", true);
                return specFlag.build();

            }
        }

        if ((Objects.isNull(keyWord)) || keyWord.equals("")) {
            return specEmp.build();
        }
        if (Objects.isNull(strWhere) || strWhere.trim().equals("")) {
            return specEmp.build();
        }
        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        for (String s : lstWhere) {

            field = Arrays.asList(clazz.getDeclaredFields())
                    .stream().filter(f -> f.getName().toLowerCase().equals(s.toLowerCase())).findFirst().orElse(null);

            if (Objects.nonNull(field)) {

                if (field.getType().equals(String.class))
                    specEmp.like(s, "%" + keyWord + "%");
                else
                    specEmp.eq(s, keyWord);
            }

        }
        if (haveDelFlag) {
            specFlag.eq("delFlag", false);
            return specFlag.predicate(specEmp.build()).build();

        } else {
            return specEmp.build();
        }
    }

    /**
     * 根据 Query 对象构建 MVEL 兼容的表达式字符串
     *
     * @param query Query 对象
     * @param <T>   实体类型
     * @return MVEL 表达式字符串
     */
    public static <T> String getQueryWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        String strWhere = query.getWhere();
        String keyWord = query.getKeyWord();
        if (Objects.isNull(strWhere) || Objects.isNull(keyWord))
            return "";
        boolean haveDelFlag = false;
        Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
        Class clazz = (Class) params[0];

        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        String express = "";
        String template = " `%s`.contains('%s') ";
        String templateInt = "`%s`==%s";
        for (String s : lstWhere) {

            Field field = Arrays.asList(clazz.getDeclaredFields())
                    .stream().filter(f -> f.getName().toLowerCase().equals(s.toLowerCase())).findFirst().orElse(null);

            if (Objects.nonNull(field)) {

                if (field.getType().equals(String.class)) {
                    if (StrUtil.isEmpty(express))
                        express = String.format(template, s, keyWord);
                    else
                        express = express.concat(" || ").concat(String.format(template, s, keyWord));
                } else
                    express = String.format(templateInt, s, keyWord);
            }

        }
        return express;
    }
}
