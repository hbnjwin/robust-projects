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

public class SpecificationBuilder {

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

    public static <T> Specification<T> getWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        String strWhere = query.getWhere();
        String keyWord = query.getKeyWord();
        boolean haveDelFlag = false;
        Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
        Class clazz = (Class) params[0];
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
