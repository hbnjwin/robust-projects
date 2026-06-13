package com.linkyoyo.reportaudit.support;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

/**
 * 字符串工具类
 * 从 CommonFunc 中提取的字符串操作方法
 */
public class StringUtils {

    /**
     * 提取两个分隔符之间的子字符串（使用 indexOf 查找结束符）
     *
     * @param content 源字符串
     * @param sourStr 开始分隔符
     * @param destStr 结束分隔符
     * @return 两个分隔符之间的内容，未找到返回 null
     */
    public static String getString(String content, String sourStr, String destStr) {
        int fromPos = content.indexOf(sourStr);
        if (fromPos == -1) {
            return null;
        }
        fromPos += sourStr.length();
        String newContent = content.substring(fromPos);
        int endPos = newContent.indexOf(destStr);
        if (endPos == -1) {
            return null;
        }
        return newContent.substring(0, endPos).trim();
    }

    /**
     * 从字符串中截取指定开始和结束字符串之间的内容（使用 lastIndexOf 查找结束符）
     *
     * @param source 源字符串
     * @param start  开始字符串
     * @param end    结束字符串
     * @return 截取的内容，如果未找到则返回空字符串
     */
    public static String substringBetween(String source, String start, String end) {
        if (source == null || start == null || end == null) {
            return "";
        }

        int startIndex = source.indexOf(start);
        if (startIndex == -1) {
            return "";
        }

        startIndex += start.length();
        // 找到最后一个结束字符
        int endIndex = source.lastIndexOf(end);
        if (endIndex == -1 || endIndex <= startIndex) {
            return "";
        }

        return source.substring(startIndex, endIndex);
    }

    /**
     * 按分隔符拆分字符串，去除控制字符并过滤空串
     *
     * @param content 源字符串
     * @param fgf     分隔符
     * @return 拆分后的列表
     */
    public static List<String> convertToList(String content, String fgf) {
        return Arrays.stream(content.split(fgf)).map(f -> {
            return f.replaceAll("\\p{C}", "").trim();
        }).filter(f -> !f.equals("")).collect(Collectors.toList());
    }
}
