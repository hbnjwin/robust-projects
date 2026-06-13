package com.linkyoyo.reportaudit.util;

import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.entity.SysOperator;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import javax.servlet.http.HttpServletRequest;
import java.util.Objects;
import cn.hutool.core.bean.BeanUtil;

//@Component
public class SysUserUtils {

    public static SysOperator currentUser() {

        HttpServletRequest request = ((ServletRequestAttributes) Objects
                .requireNonNull(RequestContextHolder.getRequestAttributes())).getRequest();

        SysOperator sysOperator = new SysOperator();
        try {
            Object obj = request.getSession().getAttribute("sysUser");
            if  (obj != null) {
                JSONObject jsonObject = new JSONObject(obj);
                BeanUtil.copyProperties(jsonObject, sysOperator);

            }
        }catch (Exception e)
        {

        }
        return  sysOperator;
    }

}
