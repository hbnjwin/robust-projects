package com.linkyoyo.reportaudit.support;

import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class StringParseUtils {

    public static List<String> convertToList(String content, String fgf) {
        return Arrays.stream(content.split(fgf)).map(f -> {
            return f.replaceAll("\\p{C}", "").trim();
        }).filter(f -> !f.equals("")).collect(Collectors.toList());
    }

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

    public static String substringBetween(String source, String start, String end) {
        if (source == null || start == null || end == null) {
            return "";
        }

        int startIndex = source.indexOf(start);
        if (startIndex == -1) {
            return "";
        }

        startIndex += start.length();
        int endIndex = source.lastIndexOf(end);
        if (endIndex == -1 || endIndex <= startIndex) {
            return "";
        }

        return source.substring(startIndex, endIndex);
    }
}
