package com.linkyoyo.reportaudit.support;

import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class DateTimeUtils {

    public static String getBegindate(String beginDate) {
        if (StringParseUtils.getString(beginDate + "@", " ", ":").compareTo("12") < 0) {
            return StringParseUtils.getString("@" + beginDate, "@", " ") + " 08:00";
        } else {
            return StringParseUtils.getString("@" + beginDate, "@", " ") + " 20:00";
        }
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
}
