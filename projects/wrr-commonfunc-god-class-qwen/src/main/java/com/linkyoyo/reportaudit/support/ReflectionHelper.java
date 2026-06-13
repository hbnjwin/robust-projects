package com.linkyoyo.reportaudit.support;

import cn.hutool.core.date.DateUtil;
import lombok.extern.slf4j.Slf4j;

import java.lang.reflect.Field;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.*;

/**
 * 反射工具类
 * 从 CommonFunc 中提取的反射字段访问和反射排序操作
 */
@Slf4j
public class ReflectionHelper {

    /**
     * 通过反射设置对象的字段值
     * 对 Date 类型会自动解析字符串
     *
     * @param clazz      目标对象
     * @param fieldName  字段名
     * @param fieldValue 字段值
     */
    public static void setField(Object clazz, String fieldName, Object fieldValue) {
        try {
            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field == null)
                return;
            field.setAccessible(true);
            if (field.isAccessible()) {
                if (field.getType() == Date.class)
                    field.set(clazz, DateUtil.parse((String) fieldValue, "yyyy-MM-dd"));
                else
                    field.set(clazz, fieldValue);
            }
        } catch (NoSuchFieldException | IllegalAccessException e) {
            throw new RuntimeException(e);
        }
    }

    /**
     * 通过反射获取对象字段值（String/Date 类型加单引号包裹）
     *
     * @param clazz     目标对象
     * @param fieldName 字段名
     * @return 字段值字符串，String/Date 类型会加单引号
     */
    public static String getFieldValue(Object clazz, String fieldName) {
        try {
            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field == null)
                return null;
            field.setAccessible(true);
            if (field.isAccessible()) {
                if (field.getType() == String.class || field.getType() == Date.class || field.getType() == Date.class)
                    return Objects.isNull(field.get(clazz)) ? "''" : "'" + field.get(clazz).toString() + "'";
                else
                    return Objects.isNull(field.get(clazz)) ? "" : field.get(clazz).toString();
            }
            return null;
        } catch (NoSuchFieldException | IllegalAccessException e) {
            log.error(String.format("获取字段%s 值错误:" + e.getMessage(), fieldName));
            return null;
        }
    }

    /**
     * 通过反射获取对象字段值（不加引号，直接 toString）
     *
     * @param clazz     目标对象
     * @param fieldName 字段名
     * @return 字段值字符串
     */
    public static String getFieldNormalValue(Object clazz, String fieldName) {
        try {
            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field == null)
                return null;
            field.setAccessible(true);
            if (field.isAccessible())
                return Objects.isNull(field.get(clazz)) ? null : field.get(clazz).toString();

            return null;
        } catch (NoSuchFieldException | IllegalAccessException e) {
            log.error(String.format("获取字段%s 值错误:" + e.getMessage(), fieldName));
            return null;
        }
    }

    /**
     * 基于反射的列表排序
     * 根据 Query 对象中的 sort 和 order 字段对列表进行排序
     *
     * @param list  要排序的列表
     * @param query 包含排序字段和方向的 Query 对象
     * @param <T>   元素类型
     */
    public static <T> void sortList(List<T> list, com.linkyoyo.reportaudit.query.Query<T> query) {
        if (query == null || query.getSort() == null || query.getSort().isEmpty()) {
            return;
        }

        list.sort(new Comparator<T>() {
            @Override
            public int compare(T o1, T o2) {

                Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
                Class clazz = (Class) params[0];

                Field field = Arrays.asList(clazz.getDeclaredFields())
                        .stream().filter(f -> f.getName().toLowerCase().equals(query.getSort().toLowerCase())).findFirst().orElse(null);
                Boolean sortAsc = Objects.isNull(query.getOrder()) ? true : query.getOrder().equalsIgnoreCase("asc") ? true : false;
                if (Objects.nonNull(field)) {

                    field.setAccessible(true);
                    if (field.isAccessible()) {

                        try {
                            String data1 = Objects.isNull(field.get(o1)) ? "" : field.get(o1).toString();
                            String data2 = Objects.isNull(field.get(o2)) ? "" : field.get(o2).toString();
                            if (sortAsc)
                                return data1.compareTo(data2);
                            else
                                return data2.compareTo(data1);

                        } catch (IllegalAccessException e) {
                            throw new RuntimeException(e);
                        }
                    }
                }
                return 0;
            }
        });
    }
}
