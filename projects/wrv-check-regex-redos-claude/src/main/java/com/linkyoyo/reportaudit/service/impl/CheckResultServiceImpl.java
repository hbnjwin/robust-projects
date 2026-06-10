package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.CheckItems;
import org.springframework.stereotype.Service;
import java.util.regex.*;

@Service
public class CheckResultServiceImpl {
    public String executeCheck(CheckItems item, String documentContent) {
        if (item.getRegex() != null && !item.getRegex().isEmpty()) {
            Pattern pattern = Pattern.compile(item.getRegex());
            Matcher matcher = pattern.matcher(documentContent);
            if (matcher.find()) {
                return "PASS";
            }
        }
        return "FAIL";
    }
}
