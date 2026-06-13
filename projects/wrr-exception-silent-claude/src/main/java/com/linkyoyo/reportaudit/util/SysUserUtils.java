package com.linkyoyo.reportaudit.util;

import cn.hutool.json.JSONObject;
import com.linkyoyo.reportaudit.entity.SysOperator;
import com.linkyoyo.reportaudit.exception.BizException;
import com.linkyoyo.reportaudit.result.CodeMsg;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import javax.servlet.http.HttpServletRequest;
import java.util.Objects;
import cn.hutool.core.bean.BeanUtil;

@Slf4j
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
        } catch (Exception e) {
            log.error("会话用户数据解析失败", e);
            throw new BizException(new CodeMsg(500, "会话数据异常，请重新登录"), e);
        }
        return  sysOperator;
    }

}
