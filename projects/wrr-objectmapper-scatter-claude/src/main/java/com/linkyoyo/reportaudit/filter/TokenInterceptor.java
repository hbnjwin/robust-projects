package com.linkyoyo.reportaudit.filter;

import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.QSysOperator;
import com.linkyoyo.reportaudit.entity.SysOperator;
import com.linkyoyo.reportaudit.security.JwtUtil;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.io.IOException;

public class TokenInterceptor implements HandlerInterceptor {

    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String AUTHORIZATION_TYPE = "Bearer";


//    private final SysOperatorRepository sysOperatorRepository;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws IOException {


        String authorizationHeader = request.getHeader(AUTHORIZATION_HEADER);

        // 检查头信息是否以Bearer开头
        if (authorizationHeader == null || !authorizationHeader.startsWith(AUTHORIZATION_TYPE)) {
            // 如果没有Bearer Token，返回401 Unauthorized
            response.setContentType("text/html;charset=utf-8");
            response.getOutputStream().write("未经授权验证的访问！".getBytes());
            return false;
        }

        // 获取Token字符串
        String token = authorizationHeader.replace(AUTHORIZATION_TYPE, "").trim();

        // 验证token的逻辑
        String returnMessage = JwtUtil.validateToken(token);
        JSONObject json;
        Boolean isExpired = false;
        if (!StrUtil.isEmpty(returnMessage)) {
            json = JSONUtil.parseObj(returnMessage);
            isExpired = json.getBool("tokenExpired");
        }

        boolean isTokenValid = returnMessage.isEmpty() || isExpired ? false : true;

        if (isTokenValid) {
            // 如果token有效，则继续链路
            json = JSONUtil.parseObj(returnMessage);
            String userId = json.getStr("userId");
            HttpSession session = request.getSession() ;
//            if (session.isNew())
            {
              session.setAttribute("userId", userId);
              session.setAttribute("sysUser", json.getStr("sysUser"));
            }
            return true;
        } else {
            response.setContentType("text/html;charset=utf-8");
            if (StrUtil.isEmptyIfStr(returnMessage)) {
                response.getOutputStream().write("未经授权验证的访问！".getBytes());
            } else {
                json = JSONUtil.parseObj(returnMessage);
                String userId = json.getStr("userId");
                ObjectMapper objectMapper = new ObjectMapper();
                SysOperator sysOperator = objectMapper.readValue(json.getStr("sysUser"), SysOperator.class);
                token = JwtUtil.generateToken(sysOperator);
                json = new JSONObject();
                json.put("code", 401) ;
                json.put("warning", "token 已经过期！");
                json.put("refreshToken", token);
                response.getOutputStream().write(json.toString().getBytes());
            }
            return false;

        }


    }


}