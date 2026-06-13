package com.linkyoyo.reportaudit.support;

import cn.hutool.core.collection.CollectionUtil;
import cn.hutool.core.date.DateUtil;
import cn.hutool.core.util.StrUtil;
import com.github.wenhao.jpa.PredicateBuilder;
import com.github.wenhao.jpa.Specifications;
import com.google.common.collect.Lists;
import com.linkyoyo.reportaudit.query.CommonQueryInfo;
import com.querydsl.jpa.impl.JPAQueryFactory;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.collections.CollectionUtils;
import org.hibernate.query.NativeQuery;
import org.hibernate.transform.Transformers;
import org.mvel2.MVEL;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import javax.persistence.EntityManager;
import javax.persistence.EntityManagerFactory;
import javax.persistence.Query;
import java.io.*;
import java.lang.reflect.Field;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.stream.Collectors;


@Component
@Slf4j
public class CommonFunc {

    @Autowired
    private JPAQueryFactory jpaQueryFactory;

    @Autowired
    public EntityManagerFactory entityManagerFactory;

    public static void clearEntityManager(EntityManager em) {
       try {
           if (Objects.nonNull(em) )
               em.clear();
       }
       catch(Exception e)
       {
           log.error("clearEntityManager error:{}",e.getMessage());
       }
    }

    public static String getBegindate(String beginDate) {
        if (CommonFunc.getString(beginDate + "@", " ", ":").compareTo("12") < 0) {
            return getString("@" + beginDate, "@", " ") + " 08:00";
        } else {
            return getString("@" + beginDate, "@", " ") + " 20:00";
        }
    }

    public static void deleteFolder(File folder) throws Exception {
        if (!folder.exists()) {
            throw new Exception("文件不存在");
        }
        File[] files = folder.listFiles();
        if (files != null) {
            for (File file : files) {
                if (file.isDirectory()) {
                    deleteFolder(file);
                } else {
                    file.delete();
                }
            }
        }
        folder.delete();
    }

    public static <T> List<List<T>> splitList(List<T> list, int groupSize) {
        int length = list.size();
        int num = (length + groupSize - 1) / groupSize;
        List<List<T>> newList = new ArrayList<>(num);
        for (int i = 0; i < num; i++) {
            int fromIndex = i * groupSize;
            int toIndex = (i + 1) * groupSize < length ? (i + 1) * groupSize : length;
            newList.add(list.subList(fromIndex, toIndex));
        }
        return newList;
    }

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

    public static List<String> convertToList(String content, String fgf) {
        return Arrays.stream(content.split(fgf)).map(f -> {
            return f.replaceAll("\p{C}", "").trim();
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

    public static Long getTimestamp(String time, String dateFormat) {
        Long timestamp = null;
        try {
            timestamp = new SimpleDateFormat(dateFormat, Locale.US).parse(time).getTime();
        } catch (ParseException e) {
            e.printStackTrace();
        }
        return timestamp;
    }

    public static String getStringTime(Long timestamp, String dateFormat) {
        if (timestamp == null) {
            return null;
        }
        String datetime = new SimpleDateFormat(dateFormat, Locale.US).format(new Date(timestamp));
        return datetime;
    }

    public static Node findTreeNode(List<Node> lstNode, String nodeId) {
        for (Node node : lstNode) {
            if (node.getId().equals(nodeId)) {
                return node;
            }
            if (node.getChildren() != null) {
                Node newNode = findTreeNode(node.getChildren(), nodeId);
                if (newNode != null) {
                    return newNode;
                }
            }
        }
        return null;
    }

    public static void addTreeNode(List<Node> lstNode, List<Node> root, Node node) {
        Node parentNode = findTreeNode(root, node.getParentId());
        if (parentNode != null) {
            if (Objects.isNull(parentNode.getChildren()) || findTreeNode(parentNode.getChildren(), node.getId()) == null)
                parentNode.addChild(node);
        } else {
            if (node.getParentId() == null || node.getParentId().equals("")) {
                if (findTreeNode(root, node.getId()) == null)
                    root.add(node);
            } else {
                Node parentNode1 = CollectionUtil.findOneByField(lstNode, "id", node.getParentId());
                Node newNode = Node.builder().id(parentNode1.getId())
                        .text(parentNode1.getText())
                        .parentId(parentNode1.getParentId()).build();
                newNode.addChild(node);
                addTreeNode(lstNode, root, newNode);
            }
        }
    }

    public static void setField(Object clazz, String fieldName, Object fieldValue) {
        try {
            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field==null)
                return ;
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
            if (field==null)
                return null;
            field.setAccessible(true);
            if (field.isAccessible()) {
                if (field.getType() == String.class || field.getType()== Date.class)
                    return Objects.isNull(field.get(clazz))?"''": "'"+field.get(clazz).toString()+"'";
                else
                    return Objects.isNull(field.get(clazz))?"":field.get(clazz).toString();
            }
            return null;
        } catch (NoSuchFieldException | IllegalAccessException e) {
            log.error( String.format( "获取字段%s 值错误:"+e.getMessage(), fieldName ));
            return null;
        }
    }

    public static String getFieldNormalValue(Object clazz, String fieldName) {
        try {
            Field field = clazz.getClass().getDeclaredField(fieldName);
            if (field==null)
                return null;
            field.setAccessible(true);
            if (field.isAccessible())
                return Objects.isNull(field.get(clazz))?null:field.get(clazz).toString();
            return null;
        } catch (NoSuchFieldException | IllegalAccessException e) {
            log.error( String.format( "获取字段%s 值错误:"+e.getMessage(), fieldName ));
            return null;
        }
    }

    public static String phraseField(Object clazz, String fieldFlag, String expression) {
        if (!expression.contains(fieldFlag))
            return expression;
        String fieldName = getString(expression, fieldFlag, fieldFlag);
        String content = getFieldValue(clazz, fieldName);
        expression = expression.replaceAll(fieldFlag+fieldName+fieldFlag, content);
        return phraseField(clazz, fieldFlag, expression);
    }

    public static <T> List<T> getFilter(List<T> lstContent, String expression, String fieldFlag) {
        return lstContent.parallelStream().filter(f -> {
            String newContent = phraseField(f, fieldFlag, expression);
            return (Boolean) MVEL.eval(newContent);
        }).collect(Collectors.toList());
    }

    public static <T> String getQueryWhere(com.linkyoyo.reportaudit.query.Query<T> query) {
        String strWhere = query.getWhere();
        String keyWord = query.getKeyWord();
        if (Objects.isNull(strWhere) || Objects.isNull(keyWord))
            return "";
        Type[] params = ((ParameterizedType) query.getClass().getGenericSuperclass()).getActualTypeArguments();
        Class clazz = (Class) params[0];
        List<String> lstWhere = Arrays.asList(strWhere.split(","));
        String express = "";
        String template=" `%s`.contains('%s') ";
        String templateInt="`%s`==%s";
        for (String s : lstWhere) {
            Field field = Arrays.asList(clazz.getDeclaredFields())
                    .stream().filter(f -> f.getName().toLowerCase().equals(s.toLowerCase())).findFirst().orElse(null);
            if (Objects.nonNull(field)) {
                if (field.getType().equals(String.class)) {
                    if (StrUtil.isEmpty(express))
                        express = String.format(template, s, keyWord);
                    else
                        express = express.concat(" || ").concat(String.format(template, s, keyWord));
                }
                else
                    express = String.format(templateInt, s, keyWord);
            }
        }
        return express;
    }

    public static <T> Page<T> convertList2PageVO(final List<T> list, final Pageable pageable) {
        if (CollectionUtils.isEmpty(list)) {
            return new PageImpl(new ArrayList<>(0), pageable, 0);
        }
        final List<T> ingredientVOS = list;
        final List<List<T>> partition = Lists.partition(list, pageable.getPageSize());
        List<T> pageContent = partition.get(pageable.getPageNumber());
        return new PageImpl<>(pageContent, pageable, ingredientVOS.size());
    }

    public static <T> Page<T> startPage(List<T> list, Pageable pageable) {
        int total = list.size();
        if (CollectionUtil.isEmpty(list)) {
            return new PageImpl<>(new ArrayList<>(), pageable, total);
        }
        int pageNum = pageable.getPageNumber() + 1;
        int pageSize = pageable.getPageSize();
        int count = list.size();
        int pageCount;
        if (count % pageSize == 0) {
            pageCount = count / pageSize;
        } else {
            pageCount = count / pageSize + 1;
        }
        int fromIndex;
        int toIndex;
        if (pageNum != pageCount) {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = fromIndex + pageSize;
        } else {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = count;
        }
        List<T> pageList = new ArrayList<>();
        if (list.size() >= toIndex) {
            pageList = Optional.of(list.subList(fromIndex, toIndex)).orElse(new ArrayList<>());
        } else if (fromIndex < list.size()) {
            pageList = Optional.of(list.subList(fromIndex, list.size())).orElse(new ArrayList<>());
        }
        return new PageImpl<>(pageList, pageable, total);
    }

    public static <T> Page<T> startPage(List<T> list, long total, Pageable pageable) {
        if (CollectionUtil.isEmpty(list)) {
            return new PageImpl<>(new ArrayList<>(), pageable, total);
        }
        int pageNum = pageable.getPageNumber() + 1;
        int pageSize = pageable.getPageSize();
        int count = list.size();
        int pageCount;
        if (count % pageSize == 0) {
            pageCount = count / pageSize;
        } else {
            pageCount = count / pageSize + 1;
        }
        int fromIndex;
        int toIndex;
        if (pageNum != pageCount) {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = fromIndex + pageSize;
        } else {
            fromIndex = (pageNum - 1) * pageSize;
            toIndex = count;
        }
        List<T> pageList = new ArrayList<>();
        if (list.size() >= toIndex) {
            pageList = Optional.of(list.subList(fromIndex, toIndex)).orElse(new ArrayList<>());
        } else if (fromIndex < list.size()) {
            pageList = Optional.of(list.subList(fromIndex, list.size())).orElse(new ArrayList<>());
        }
        return new PageImpl<>(pageList, pageable, total);
    }

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
                Boolean sortAsc = Objects.isNull(query.getOrder())?true:query.getOrder().equalsIgnoreCase("asc")?true:false;
                if (Objects.nonNull(field)) {
                    field.setAccessible(true);
                    if (field.isAccessible()) {
                        try {
                           String data1= Objects.isNull(field.get(o1))?"":field.get(o1).toString();
                           String data2= Objects.isNull(field.get(o2))?"":field.get(o2).toString();
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

    public static File createTempFile(byte[] bytes, String fileName, String fileExtension) throws IOException {
        ByteArrayInputStream bis = new ByteArrayInputStream(bytes);
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        byte[] buffer = new byte[1024];
        int read;
        while ((read = bis.read(buffer)) != -1) {
            bos.write(buffer, 0, read);
        }
        File tempFile = File.createTempFile(fileName, fileExtension);
        try (FileOutputStream fos = new FileOutputStream(tempFile)) {
            fos.write(bos.toByteArray());
        }
        return tempFile;
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
