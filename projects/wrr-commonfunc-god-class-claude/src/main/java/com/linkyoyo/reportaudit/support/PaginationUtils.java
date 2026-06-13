package com.linkyoyo.reportaudit.support;

import cn.hutool.core.collection.CollectionUtil;
import com.google.common.collect.Lists;
import org.apache.commons.collections.CollectionUtils;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;

import java.lang.reflect.Field;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.*;

public class PaginationUtils {

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
