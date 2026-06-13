package com.linkyoyo.reportaudit.support;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 日期时间工具类
 * 从 CommonFunc 中提取的日期时间格式化操作
 */
public class DateTimeUtils {

    /**
     * 根据小时判断是上午还是下午，返回带固定时间的日期字符串
     *
     * @param beginDate 原始日期字符串
     * @return 带 "08:00" 或 "20:00" 后缀的日期字符串
     */
    public static String getBegindate(String beginDate) {
        if (StringUtils.getString(beginDate + "@", " ", ":").compareTo("12") < 0) {
            return StringUtils.getString("@" + beginDate, "@", " ") + " 08:00";
        } else {
            return StringUtils.getString("@" + beginDate, "@", " ") + " 20:00";
        }
    }

    /**
     * 字符串转时间戳
     *
     * @param time       时间字符串
     * @param dateFormat 日期格式，如 "yyyy-MM-dd HH:mm:ss"
     * @return 时间戳（毫秒）
     */
    public static Long getTimestamp(String time, String dateFormat) {
        Long timestamp = null;
        try {
            timestamp = new SimpleDateFormat(dateFormat, Locale.US).parse(time).getTime();
        } catch (ParseException e) {
            e.printStackTrace();
        }
        return timestamp;
    }

    /**
     * 时间戳转字符串
     *
     * @param timestamp  时间戳（毫秒）
     * @param dateFormat 日期格式，如 "yyyy-MM-dd HH:mm:ss"
     * @return 格式化后的时间字符串
     */
    public static String getStringTime(Long timestamp, String dateFormat) {
        if (timestamp == null) {
            return null;
        }
        String datetime = new SimpleDateFormat(dateFormat, Locale.US).format(new Date(timestamp));
        return datetime;
    }
}
