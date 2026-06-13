package com.linkyoyo.reportaudit.util;

import java.util.*;
import java.util.regex.Pattern;
import java.util.regex.Matcher;
import java.io.*;
import java.nio.file.*;

/**
 * 处理真实原始文件的章节整理程序
 */
public class ProcessRealFile {
    
    public static void main(String[] args) {
        String inputFile = "./d:/data/upload/5918e5c2-1cf8-4f78-87fb-ed86bf1f475f/GW-12WG.0112 金风机组微观选址复核报告(大唐河南许昌鄢陵10MW项目)_A0.md";
        String outputCleanedFile = "./doc/test/GW12WG_final_processed_cleaned.md";
        String outputTocFile = "./doc/test/GW12WG_final_processed_toc.json";
        
        try {
            String content = new String(Files.readAllBytes(Paths.get(inputFile)));
            System.out.println("=== 处理真实原始文件 ===");
            System.out.println("文件路径: " + inputFile);
            System.out.println("文件大小: " + content.length() + " 字符");
            System.out.println();
            
            String result = processRealFile(content, "GW12WG_final_processed");
            
            System.out.println("=== 处理完成 ===");
            System.out.println("结果已保存到 ./doc/test/ 目录");
            
        } catch (IOException e) {
            System.err.println("读取文件失败: " + e.getMessage());
        }
    }
    
    /**
     * 只传入mdContent的处理方法，返回处理结果
     */
    public static Map<String, Object> processMarkdownContent(String markdownContent) {
        String[] lines = markdownContent.split("\n");
        StringBuilder cleanedMarkdown = new StringBuilder();
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> toc = new ArrayList<>();
        
        String currentChapter = null;
        String currentNormalizedTitle = null;
        StringBuilder currentContent = new StringBuilder();
        boolean startProcessing = false;
        int chapterCount = 0;
        
        // 先找到第一个真实章节的位置（跳过目录）
        int firstChapterIndex = -1;
        boolean inTableOfContents = false;
        
        for (int i = 0; i < lines.length; i++) {
            String line = lines[i].trim();
            
            // 检测目录开始标志
            if (line.contains("目录") || line.contains("目 录") || line.toLowerCase().contains("content")) {
                inTableOfContents = true;
                continue;
            }
            
            // 检测目录结束标志（遇到真正的章节标题）
            if (inTableOfContents) {
                // 如果遇到以#开头的标题，说明目录结束，正文开始
                if (line.matches("^#+\\s*[0-9]+[\\.．\\s].*")) {
                    firstChapterIndex = i;
                    break;
                }
                // 如果遇到明显的章节分隔符或正文开始标志，目录结束
                if (line.contains("---") || line.contains("===") || 
                    line.contains("正文") || line.contains("报告") ||
                    line.matches("^#+\\s*[^0-9].*")) {
                    inTableOfContents = false;
                }
                continue;
            }
            
            // 寻找正文中的第一个主要章节
            // 1. 以#开头包含"1"编号的章节
            if (line.matches("^#\\s*1[\\.．\\s].*")) {
                firstChapterIndex = i;
                break;
            }
            // 2. 以##开头包含数字编号的章节
            if (line.matches("^#{2,6}\\s*1[\\.．].*")) {
                firstChapterIndex = i;
                break;
            }
            // 3. 特殊格式：直接以"1"开头的章节（如："1 工程概述"）
            // 但要排除目录项（通常包含很多点号）
            if (line.matches("^1[\\.．\\s].*") && !line.matches(".*\\d+\\.\\d+.*") && 
                !line.matches(".*\\.{3,}.*")) { // 排除包含连续点号的目录项
                firstChapterIndex = i;
                break;
            }
        }
        
        if (firstChapterIndex == -1) {
            // 未找到真实章节，返回原文档
            result.put("cleanedMarkdown", markdownContent);
            result.put("tableOfContents", new ArrayList<>());
            result.put("totalChapters", 0);
            return result;
        }
        
        // 添加前言部分（第一个真实章节之前的内容）
        for (int i = 0; i < firstChapterIndex; i++) {
            cleanedMarkdown.append(lines[i]).append("\n");
        }
        
        // 处理真实章节
        for (int i = firstChapterIndex; i < lines.length; i++) {
            String line = lines[i];
            String trimmedLine = line.trim();
            
            if (isRealChapterTitle(trimmedLine)) {
                // 规范化标题格式
                String normalizedTitle = normalizeTitle(trimmedLine);
                
                // 保存上一章节
                if (currentChapter != null && currentContent.length() > 0) {
                    Map<String, Object> chapterInfo = new LinkedHashMap<>();
                    chapterInfo.put("title", currentNormalizedTitle);
                    chapterInfo.put("content", currentContent.toString().trim());
                    chapterInfo.put("originalLine", currentChapter);
                    chapterInfo.put("lineNumber", i);
                    toc.add(chapterInfo);
                    chapterCount++;
                }
                
                // 开始新章节
                currentChapter = trimmedLine;
                currentNormalizedTitle = normalizedTitle;
                currentContent = new StringBuilder();
                
                cleanedMarkdown.append(normalizedTitle).append("\n\n");
                
            } else {
                // 普通内容行
                cleanedMarkdown.append(line).append("\n");
                if (currentChapter != null) {
                    currentContent.append(line).append("\n");
                }
            }
        }
        
        // 保存最后一章节
        if (currentChapter != null && currentContent.length() > 0) {
            Map<String, Object> chapterInfo = new LinkedHashMap<>();
            chapterInfo.put("title", currentNormalizedTitle);
            chapterInfo.put("content", currentContent.toString().trim());
            chapterInfo.put("originalLine", currentChapter);
            chapterInfo.put("lineNumber", lines.length);
            toc.add(chapterInfo);
            chapterCount++;
        }
        
        result.put("cleanedMarkdown", cleanedMarkdown.toString());
        result.put("tableOfContents", toc);
        result.put("totalChapters", chapterCount);
        
        return result;
    }

    /**
     * 处理真实文件的方法
     */
    public static String processRealFile(String markdownContent, String fileName) {
        String[] lines = markdownContent.split("\n");
        StringBuilder cleanedMarkdown = new StringBuilder();
        Map<String, Object> result = new LinkedHashMap<>();
        List<Map<String, Object>> toc = new ArrayList<>();
        
        String currentChapter = null;
        String currentNormalizedTitle = null;
        StringBuilder currentContent = new StringBuilder();
        boolean startProcessing = false;
        int chapterCount = 0;
        
        System.out.println("开始分析文档结构...");
        
        // 先找到第一个真实章节的位置（跳过目录）
        // 寻找正文开始的标志：通常是 "### 1．项目综述和概况" 这样的格式
        int firstChapterIndex = -1;
        boolean inTableOfContents = false;
        
        for (int i = 0; i < lines.length; i++) {
            String line = lines[i].trim();
            
            // 检测目录开始标志
            if (line.contains("目录") || line.contains("目 录") || line.toLowerCase().contains("content")) {
                inTableOfContents = true;
                System.out.println("检测到目录开始在第 " + (i + 1) + " 行: " + line);
                continue;
            }
            
            // 检测目录结束标志（遇到真正的章节标题）
            if (inTableOfContents) {
                // 如果遇到以#开头的标题，说明目录结束，正文开始
                if (line.matches("^#+\\s*[0-9]+[\\.．\\s].*")) {
                    firstChapterIndex = i;
                    System.out.println("目录结束，找到第一个真实章节在第 " + (i + 1) + " 行: " + line);
                    break;
                }
                // 如果遇到明显的章节分隔符或正文开始标志，目录结束
                if (line.contains("---") || line.contains("===") || 
                    line.contains("正文") || line.contains("报告") ||
                    line.matches("^#+\\s*[^0-9].*")) {
                    inTableOfContents = false;
                    System.out.println("检测到目录结束标志在第 " + (i + 1) + " 行: " + line);
                }
                continue;
            }
            
            // 寻找正文中的第一个主要章节
            // 1. 以#开头包含"1"编号的章节
            if (line.matches("^#\\s*1[\\.．\\s].*")) {
                firstChapterIndex = i;
                System.out.println("找到第一个真实章节在第 " + (i + 1) + " 行: " + line);
                break;
            }
            // 2. 以##开头包含数字编号的章节
            if (line.matches("^#{2,6}\\s*1[\\.．].*")) {
                firstChapterIndex = i;
                System.out.println("找到第一个真实章节在第 " + (i + 1) + " 行: " + line);
                break;
            }
            // 3. 特殊格式：直接以"1"开头的章节（如："1 工程概述"）
            // 但要排除目录项（通常包含很多点号）
            if (line.matches("^1[\\.．\\s].*") && !line.matches(".*\\d+\\.\\d+.*") && 
                !line.matches(".*\\.{3,}.*")) { // 排除包含连续点号的目录项
                firstChapterIndex = i;
                System.out.println("找到第一个真实章节在第 " + (i + 1) + " 行: " + line);
                break;
            }
        }
        
        if (firstChapterIndex == -1) {
            System.out.println("未找到真实章节，返回原文档");
            return markdownContent;
        }
        
        // 添加前言部分（第一个真实章节之前的内容）
        for (int i = 0; i < firstChapterIndex; i++) {
            cleanedMarkdown.append(lines[i]).append("\n");
        }
        
        // 处理真实章节
        for (int i = firstChapterIndex; i < lines.length; i++) {
            String line = lines[i];
            String trimmedLine = line.trim();
            
            if (isRealChapterTitle(trimmedLine)) {
                // 规范化标题格式
                String normalizedTitle = normalizeTitle(trimmedLine);
                
                // 保存上一章节
                if (currentChapter != null && currentContent.length() > 0) {
                    Map<String, Object> chapterInfo = new LinkedHashMap<>();
                    chapterInfo.put("title", currentNormalizedTitle);  // 使用规范化后的标题
                    chapterInfo.put("content", currentContent.toString().trim());
                    toc.add(chapterInfo);
                    chapterCount++;
                }
                
                // 开始新章节
                currentChapter = trimmedLine;
                currentNormalizedTitle = normalizedTitle;  // 保存规范化标题
                currentContent = new StringBuilder();
                
                cleanedMarkdown.append(normalizedTitle).append("\n\n");
                
                System.out.println("处理章节 " + (chapterCount + 1) + ": " + trimmedLine + " -> " + normalizedTitle);
                
            } else {
                // 普通内容行
                cleanedMarkdown.append(line).append("\n");
                if (currentChapter != null) {
                    currentContent.append(line).append("\n");
                }
            }
        }
        
        // 保存最后一章节
        if (currentChapter != null && currentContent.length() > 0) {
            Map<String, Object> chapterInfo = new LinkedHashMap<>();
            chapterInfo.put("title", currentNormalizedTitle);  // 使用规范化后的标题
            chapterInfo.put("content", currentContent.toString().trim());
            toc.add(chapterInfo);
            chapterCount++;
        }
        
        result.put("cleanedMarkdown", cleanedMarkdown.toString());
        result.put("tableOfContents", toc);
        result.put("totalChapters", chapterCount);
        result.put("originalLength", markdownContent.length());
        result.put("cleanedLength", cleanedMarkdown.length());
        
        System.out.println("共处理章节: " + chapterCount + " 个");
        
        // 保存文件
        saveResults(cleanedMarkdown.toString(), result, fileName);
        
        return toJson(result);
    }
    
    /**
     * 判断是否为真实章节标题（需要处理的）
     */
    private static boolean isRealChapterTitle(String line) {
        if (line == null || line.trim().isEmpty()) {
            return false;
        }
        
        // 需要处理的标题类型：
        // 1. 跳过目录中的粗体标题（这些是目录项，不是真实章节）
        // 只处理正文中的实际章节标题
        
        // 2. 主要章节：以单个#开头的标题，包含数字编号
        if (line.matches("^#\\s*[0-9]+[\\.．\\s].*") || line.matches("^#\\s*[0-9]+[^0-9\\.].*")) {
            return true;
        }
        
        // 3. 以##开头的二级章节，包含数字编号（支持有点号和无点号两种格式）
        if (line.matches("^##\\s*[0-9]+[\\.．].*") || line.matches("^##\\s*[0-9]+[^0-9\\.].*")) {
            return true;
        }
        
        // 4. 以###或更多#开头的子章节，包含数字编号（支持有点号和无点号两种格式）
        if (line.matches("^#{3,6}\\s*[0-9]+[\\.．].*") || line.matches("^#{3,6}\\s*[0-9]+[^0-9\\.].*")) {
            return true;
        }
        
        // 5. 附表格式 - 支持多种格式
        if (line.contains("附表")) {
            // ## 附表1 发电量计算结果（GW121-2000-90HH）
            if (line.matches("^#{1,6}\\s*附表.*")) {
                return true;
            }
            // **附表1 发电量计算结果（GW121-2000-90HH）**
            if (line.startsWith("**") && line.contains("附表")) {
                return true;
            }
            // 附表1 发电量计算结果（GW121-2000-90HH）
            if (line.startsWith("附表")) {
                return true;
            }
        }
        
        // 6. 特殊格式：没有#但以数字开头的章节标题（如："2电力系统一次部分"）
        if (line.matches("^[0-9]+[\\.．\\s].*") && !line.matches(".*\\d+\\.\\d+.*")) {
            return true;
        }
        
        return false;
    }
    
    /**
     * 规范化标题格式
     */
    private static String normalizeTitle(String title) {
        // 清理格式：移除 # 和 * 符号
        String cleaned = title.replaceAll("^#+\\s*", "").replaceAll("^\\*+", "").replaceAll("\\*+$", "").trim();
        
        // 处理特殊格式：如"2电力系统一次部分"（没有点号分隔）
        Pattern specialPattern = Pattern.compile("^([0-9]+)([^0-9\\.].*)"); 
        Matcher specialMatcher = specialPattern.matcher(cleaned);
        if (specialMatcher.find()) {
            String number = specialMatcher.group(1);
            String titleText = specialMatcher.group(2).trim();
            return "# " + number + ". " + titleText;
        }
        
        // 提取章节编号（标准格式）
        Pattern pattern = Pattern.compile("^([0-9]+(?:\\.[0-9]+)*)[\\.．]?\\s*(.*)");
        Matcher matcher = pattern.matcher(cleaned);
        
        if (matcher.find()) {
            String number = matcher.group(1);
            String titleText = matcher.group(2).trim();
            
            // 根据编号层级确定标题级别
            String[] parts = number.split("\\.");
            int level = parts.length;
            
            // 兼容不同文件格式的层级映射：
            // 主章节 (1, 2, 3...) -> # (一级标题)
            // 子章节 (1.1, 2.1, 3.1...) -> ## (二级标题)  
            // 子子章节 (1.1.1, 2.1.1...) -> ### (三级标题)
            StringBuilder hashPrefix = new StringBuilder();
            for (int i = 0; i < level; i++) {
                hashPrefix.append("#");
            }
            
            // 添加点号以保持格式一致
            String formattedNumber = number;
            if (!titleText.isEmpty() && !number.endsWith(".")) {
                formattedNumber = number + ".";
            }
            
            return hashPrefix.toString() + " " + formattedNumber + (titleText.isEmpty() ? "" : " " + titleText);
        }
        
        // 处理附表 - 保持原有的标题级别
        if (cleaned.contains("附表")) {
            // 如果原标题已经有#标记，保持原有级别
            if (title.startsWith("#")) {
                // 计算原有的#数量
                int hashCount = 0;
                for (char c : title.toCharArray()) {
                    if (c == '#') {
                        hashCount++;
                    } else {
                        break;
                    }
                }
                StringBuilder hashPrefix = new StringBuilder();
                for (int i = 0; i < hashCount; i++) {
                    hashPrefix.append("#");
                }
                return hashPrefix.toString() + " " + cleaned;
            } else {
                // 默认为二级标题
                return "## " + cleaned;
            }
        }
        
        // 默认为二级标题
        return "## " + cleaned;
    }
    
    /**
     * 保存结果到文件
     */
    private static void saveResults(String cleanedMdContent, Map<String, Object> resultMap, String fileName) {
        try {
            String outputDir = "./doc/test";
            Path outputPath = Paths.get(outputDir);
            if (!Files.exists(outputPath)) {
                Files.createDirectories(outputPath);
                System.out.println("创建输出目录: " + outputDir);
            }

            String baseName = new File(fileName).getName();
            if (baseName.contains(".")) {
                baseName = baseName.substring(0, baseName.lastIndexOf('.'));
            }

            // 保存整理后的Markdown内容
            String mdFilePath = outputDir + File.separator + baseName + "_cleaned.md";
            try (FileWriter mdWriter = new FileWriter(mdFilePath)) {
                mdWriter.write(cleanedMdContent);
            }
            System.out.println("已保存整理后的Markdown内容到: " + mdFilePath);

            // 保存JSON结果
            String jsonFilePath = outputDir + File.separator + baseName + "_toc.json";
            try (FileWriter jsonWriter = new FileWriter(jsonFilePath)) {
                String formattedJson = toJson(resultMap);
                jsonWriter.write(formattedJson);
            }
            System.out.println("已保存JSON结果到: " + jsonFilePath);

        } catch (IOException e) {
            System.err.println("保存结果时出错: " + e.getMessage());
        }
    }
    
    /**
     * 简化的JSON序列化方法
     */
    private static String toJson(Map<String, Object> map) {
        StringBuilder json = new StringBuilder();
        json.append("{\n");
        
        boolean first = true;
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            if (!first) {
                json.append(",\n");
            }
            first = false;
            
            json.append("  \"").append(entry.getKey()).append("\": ");
            
            Object value = entry.getValue();
            if (value instanceof String) {
                String strValue = (String) value;
                if (strValue.length() > 500 && entry.getKey().equals("cleanedMarkdown")) {
                    strValue = strValue.substring(0, 500) + "...(truncated)";
                }
                json.append("\"").append(escapeJson(strValue)).append("\"");
            } else if (value instanceof List) {
                json.append(listToJson((List<?>) value));
            } else {
                json.append(value);
            }
        }
        
        json.append("\n}");
        return json.toString();
    }
    
    private static String listToJson(List<?> list) {
        StringBuilder json = new StringBuilder();
        json.append("[\n");
        
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) {
                json.append(",\n");
            }
            
            Object item = list.get(i);
            if (item instanceof Map) {
                json.append("    ").append(mapToJson((Map<?, ?>) item, "    "));
            } else {
                json.append("    \"").append(item).append("\"");
            }
        }
        
        json.append("\n  ]");
        return json.toString();
    }
    
    private static String mapToJson(Map<?, ?> map, String indent) {
        StringBuilder json = new StringBuilder();
        json.append("{\n");
        
        boolean first = true;
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            if (!first) {
                json.append(",\n");
            }
            first = false;
            
            json.append(indent).append("  \"").append(entry.getKey()).append("\": ");
            Object value = entry.getValue();
            if (value instanceof String) {
                String strValue = (String) value;
                // 只对cleanedMarkdown进行截断，章节内容保持完整
                if (strValue.length() > 1000 && entry.getKey().equals("cleanedMarkdown")) {
                    strValue = strValue.substring(0, 1000) + "...(truncated)";
                }
                json.append("\"").append(escapeJson(strValue)).append("\"");
            } else {
                json.append(value);
            }
        }
        
        json.append("\n").append(indent).append("}");
        return json.toString();
    }
    
    private static String escapeJson(String str) {
        return str.replace("\\", "\\\\")
                  .replace("\"", "\\\"")
                  .replace("\n", "\\n")
                  .replace("\r", "\\r")
                  .replace("\t", "\\t");
    }
}
