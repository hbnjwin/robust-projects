package com.linkyoyo.reportaudit.support;

import org.mvel2.MVEL;

import java.util.List;
import java.util.stream.Collectors;

/**
 * MVEL 表达式求值工具类
 * 从 CommonFunc 中提取的 MVEL 动态过滤操作
 */
public class MvelFilterUtils {

    /**
     * 将表达式中的 @fieldName@ 占位符替换为对象的实际字段值（递归处理）
     *
     * @param clazz      目标对象
     * @param fieldFlag  字段占位符标记（如 "@"）
     * @param expression MVEL 表达式
     * @return 替换后的表达式
     */
    public static String phraseField(Object clazz, String fieldFlag, String expression) {
        if (!expression.contains(fieldFlag))
            return expression;
        String fieldName = StringUtils.getString(expression, fieldFlag, fieldFlag);
        String content = ReflectionHelper.getFieldValue(clazz, fieldName);

        expression = expression.replaceAll(fieldFlag + fieldName + fieldFlag, content);
        return phraseField(clazz, fieldFlag, expression);
    }

    /**
     * 使用 MVEL 表达式过滤列表
     *
     * @param lstContent 要过滤的列表
     * @param expression MVEL 表达式（支持 @field@ 占位符）
     * @param fieldFlag  字段占位符标记
     * @param <T>        元素类型
     * @return 过滤后的列表
     */
    public static <T> List<T> getFilter(List<T> lstContent, String expression, String fieldFlag) {
        return lstContent.parallelStream().filter(f -> {
            String newContent = phraseField(f, fieldFlag, expression);
            return (Boolean) MVEL.eval(newContent);
        }).collect(Collectors.toList());
    }
}
