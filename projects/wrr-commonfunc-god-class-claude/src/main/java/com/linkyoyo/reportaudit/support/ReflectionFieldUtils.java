package com.linkyoyo.reportaudit.support;

import cn.hutool.core.date.DateUtil;
import lombok.extern.slf4j.Slf4j;
import org.mvel2.MVEL;

import java.lang.reflect.Field;
import java.util.Date;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

@Slf4j
public class ReflectionFieldUtils {

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

    public static String phraseField(Object clazz, String fieldFlag, String expression) {
        if (!expression.contains(fieldFlag))
            return expression;
        String fieldName = StringParseUtils.getString(expression, fieldFlag, fieldFlag);
        String content = getFieldValue(clazz, fieldName);

        expression = expression.replaceAll(fieldFlag + fieldName + fieldFlag, content);
        return phraseField(clazz, fieldFlag, expression);
    }

    public static <T> List<T> getFilter(List<T> lstContent, String expression, String fieldFlag) {
        return lstContent.parallelStream().filter(f -> {
            String newContent = phraseField(f, fieldFlag, expression);
            return (Boolean) MVEL.eval(newContent);
        }).collect(Collectors.toList());
    }
}
