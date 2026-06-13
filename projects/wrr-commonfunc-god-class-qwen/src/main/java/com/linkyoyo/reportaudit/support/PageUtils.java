package com.linkyoyo.reportaudit.support;

import cn.hutool.core.collection.CollectionUtil;
import com.google.common.collect.Lists;
import org.apache.commons.collections.CollectionUtils;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * 列表分页工具类
 * 从 CommonFunc 中提取的列表分页和分割操作
 */
public class PageUtils {

    /**
     * 按照指定长度切割列表
     *
     * @param list    要分割的列表
     * @param groupSize 每组大小
     * @param <T>     元素类型
     * @return 分割后的列表集合
     */
    public static <T> List<List<T>> splitList(List<T> list, int groupSize) {
        int length = list.size();
        // 计算可以分成多少组
        int num = (length + groupSize - 1) / groupSize;
        List<List<T>> newList = new ArrayList<>(num);
        for (int i = 0; i < num; i++) {
            // 开始位置
            int fromIndex = i * groupSize;
            // 结束位置
            int toIndex = (i + 1) * groupSize < length ? (i + 1) * groupSize : length;
            newList.add(list.subList(fromIndex, toIndex));
        }
        return newList;
    }

    /**
     * List 转 Page 对象（使用 Guava partition）
     *
     * @param list     数据列表
     * @param pageable 分页参数
     * @param <T>      元素类型
     * @return Page 对象
     */
    public static <T> Page<T> convertList2PageVO(final List<T> list, final Pageable pageable) {
        if (CollectionUtils.isEmpty(list)) {
            return new PageImpl(new ArrayList<>(0), pageable, 0);
        }
        final List<T> ingredientVOS = list;
        final List<List<T>> partition = Lists.partition(list, pageable.getPageSize());
        List<T> pageContent = partition.get(pageable.getPageNumber());
        return new PageImpl<>(pageContent, pageable, ingredientVOS.size());
    }

    /**
     * 手动内存分页
     *
     * @param list     全部数据
     * @param pageable 查询条件
     * @param <T>      元素类型
     * @return Page 对象
     */
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
        int fromIndex; // 开始索引
        int toIndex; // 结束索引
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

    /**
     * 手动内存分页（指定总记录数）
     *
     * @param list     全部数据
     * @param total    List 总长度
     * @param pageable 查询条件
     * @param <T>      元素类型
     * @return Page 对象
     */
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
        int fromIndex; // 开始索引
        int toIndex; // 结束索引
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
}
