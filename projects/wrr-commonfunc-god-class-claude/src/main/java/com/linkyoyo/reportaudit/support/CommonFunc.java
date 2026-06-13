package com.linkyoyo.reportaudit.support;

import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.query.CommonQueryInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import javax.persistence.EntityManager;
import java.io.File;
import java.io.IOException;
import java.util.List;

/**
 * Thin delegation facade — preserved for backward compatibility.
 * All logic has been extracted to focused classes:
 * {@link StringParseUtils}, {@link DateTimeUtils}, {@link FileUtils},
 * {@link TreeNodeUtils}, {@link ReflectionFieldUtils}, {@link SpecificationBuilder},
 * {@link PaginationUtils}, {@link NativeQueryService}, {@link AiService}.
 */
@Component
@Slf4j
public class CommonFunc {

    @Autowired
    private NativeQueryService nativeQueryService;

    @Autowired
    private AiService aiService;

    // ==================== StringParseUtils ====================

    public static List<String> convertToList(String content, String fgf) {
        return StringParseUtils.convertToList(content, fgf);
    }

    public static String getString(String content, String sourStr, String destStr) {
        return StringParseUtils.getString(content, sourStr, destStr);
    }

    public static String substringBetween(String source, String start, String end) {
        return StringParseUtils.substringBetween(source, start, end);
    }

    // ==================== DateTimeUtils ====================

    public static String getBegindate(String beginDate) {
        return DateTimeUtils.getBegindate(beginDate);
    }

    public static Long getTimestamp(String time, String dateFormat) {
        return DateTimeUtils.getTimestamp(time, dateFormat);
    }

    public static String getStringTime(Long timestamp, String dateFormat) {
        return DateTimeUtils.getStringTime(timestamp, dateFormat);
    }

    // ==================== FileUtils ====================

    public static void deleteFolder(File folder) throws Exception {
        FileUtils.deleteFolder(folder);
    }

    public static File createTempFile(byte[] bytes, String fileName, String fileExtension) throws IOException {
        return FileUtils.createTempFile(bytes, fileName, fileExtension);
    }

    // ==================== TreeNodeUtils ====================

    public static Node findTreeNode(List<Node> lstNode, String nodeId) {
        return TreeNodeUtils.findTreeNode(lstNode, nodeId);
    }

    public static void addTreeNode(List<Node> lstNode, List<Node> root, Node node) {
        TreeNodeUtils.addTreeNode(lstNode, root, node);
    }

    // ==================== ReflectionFieldUtils ====================

    public static void setField(Object clazz, String fieldName, Object fieldValue) {
        ReflectionFieldUtils.setField(clazz, fieldName, fieldValue);
    }

    public static String getFieldValue(Object clazz, String fieldName) {
        return ReflectionFieldUtils.getFieldValue(clazz, fieldName);
    }

    public static String getFieldNormalValue(Object clazz, String fieldName) {
        return ReflectionFieldUtils.getFieldNormalValue(clazz, fieldName);
    }

    public static String phraseField(Object clazz, String fieldFlag, String expression) {
        return ReflectionFieldUtils.phraseField(clazz, fieldFlag, expression);
    }

    public static <T> List<T> getFilter(List<T> lstContent, String expression, String fieldFlag) {
        return ReflectionFieldUtils.getFilter(lstContent, expression, fieldFlag);
    }

    // ==================== SpecificationBuilder ====================

    public static <T> Specification<T> getWhere(String strWhere, String keyWord, Boolean haveDelFlag) {
        return SpecificationBuilder.getWhere(strWhere, keyWord, haveDelFlag);
    }

    public static <T> Specification<T> getWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        return SpecificationBuilder.getWhere(query);
    }

    public static <T> String getQueryWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        return SpecificationBuilder.getQueryWhere(query);
    }

    // ==================== PaginationUtils ====================

    public static <T> List<List<T>> splitList(List<T> list, int groupSize) {
        return PaginationUtils.splitList(list, groupSize);
    }

    public static <T> Page<T> convertList2PageVO(List<T> list, Pageable pageable) {
        return PaginationUtils.convertList2PageVO(list, pageable);
    }

    public static <T> Page<T> startPage(List<T> list, Pageable pageable) {
        return PaginationUtils.startPage(list, pageable);
    }

    public static <T> Page<T> startPage(List<T> list, long total, Pageable pageable) {
        return PaginationUtils.startPage(list, total, pageable);
    }

    public static <T> void sortList(List<T> list, com.linkyoyo.reportaudit.query.Query<T> query) {
        PaginationUtils.sortList(list, query);
    }

    // ==================== NativeQueryService ====================

    public static void clearEntityManager(EntityManager em) {
        NativeQueryService.clearEntityManager(em);
    }

    public List commQuery(CommonQueryInfo commonQueryInfo) {
        return nativeQueryService.commQuery(commonQueryInfo);
    }

    public List actQuery(CommonQueryInfo commonQueryInfo) {
        return nativeQueryService.actQuery(commonQueryInfo);
    }

    public List commQuerySql(String sql) {
        return nativeQueryService.commQuerySql(sql);
    }

    public String getModuleMaxValueOld(String moduleName) {
        return nativeQueryService.getModuleMaxValueOld(moduleName);
    }

    // ==================== AiService ====================

    public void CallOpenAiBySse(String baseString64, SseEmitter sseEmitter) {
        aiService.CallOpenAiBySse(baseString64, sseEmitter);
    }

    public List callOpenAi(String baseString64) {
        return aiService.callOpenAi(baseString64);
    }

    public JSONObject callNewOpenAi(String baseString64) {
        return aiService.callNewOpenAi(baseString64);
    }

    public JSONObject callAi(File file) {
        return aiService.callAi(file);
    }

    public JSONObject callAiWithOkHttp(String content) {
        return aiService.callAiWithOkHttp(content);
    }

    public JSONObject callDeepSeekAi(String content) {
        return aiService.callDeepSeekAi(content);
    }

    public JSONObject callAiWithOkHttp(String content, boolean isAzure, String url, String key,
                                       String model, String version, String promptMarkDown) {
        return aiService.callAiWithOkHttp(content, isAzure, url, key, model, version, promptMarkDown);
    }

    public JSONObject callAi(String query) {
        return aiService.callAi(query);
    }
}
