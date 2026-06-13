package com.linkyoyo.reportaudit.aop;

import cn.hutool.core.util.ObjectUtil;
import cn.hutool.core.util.URLUtil;
import cn.hutool.extra.servlet.ServletUtil;
import cn.hutool.http.HttpUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONUtil;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.annotation.SysOperaLog;
import com.linkyoyo.reportaudit.entity.SysLog;
import com.linkyoyo.reportaudit.entity.SysOperator;
import com.linkyoyo.reportaudit.repository.SysLogRepository;
import com.linkyoyo.reportaudit.util.MyStringUtils;
import lombok.AllArgsConstructor;
import lombok.SneakyThrows;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StopWatch;
import org.springframework.util.StringUtils;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import org.springframework.web.servlet.HandlerMapping;

import javax.servlet.http.HttpServletRequest;
import java.util.Date;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

@Slf4j
@Aspect
@Component
@AllArgsConstructor
public class SysOperaLogAspect {

    private final ApplicationEventPublisher publisher;

    private final ObjectMapper objectMapper;

    private final SysLogRepository sysLogRepository;

    @SneakyThrows
    @Around("@annotation(sysLog)")
    public Object around(ProceedingJoinPoint point, SysOperaLog sysLog) {

        HttpServletRequest request = ((ServletRequestAttributes) Objects
                .requireNonNull(RequestContextHolder.getRequestAttributes())).getRequest();

        ObjectMapper objectMapper = new ObjectMapper();
        SysOperator sysOperator=null;
        try {
            Object obj =request.getSession().getAttribute("sysUser");
            if  (obj != null)
                sysOperator = objectMapper.readValue(obj.toString(), SysOperator.class);
        } catch (Exception e) {
            log.warn("操作日志切面获取登录用户信息失败, 将以匿名用户记录日志", e);
        }

        StopWatch sw = new StopWatch();
        sw.start();
        Object obj = point.proceed();
        sw.stop();

        try
        {



            String body = "";


            if (!ServletUtil.isGetMethod(request) && !ServletUtil.isMultipart(request) && sysLog.isRecordBody()) {
                body = MyStringUtils.compress(ServletUtil.getBody(request));
            }
            String title = sysLog.value();
            String module = sysLog.id();
            if (!ObjectUtil.isEmpty(body)) {
                try {
                    JSONObject bodyJson = JSONUtil.parseObj(body);
                    Object value = bodyJson.get("id");
                    if (Objects.nonNull(value))
                        title = title.concat("--修改");
                    else {
                        if(!request.getRequestURI().contains("/batch"))
                            title = title.concat("--新增");
                    }
                } catch (Exception e) {
                    log.warn("操作日志切面解析请求体JSON失败, 跳过操作类型判断: {}", e.getMessage());
                }
            }





        SysLog.SysLogBuilder builder = SysLog.builder().type(Integer.parseInt(sysLog.type()))
                .title(title).remoteAddr(ServletUtil.getClientIP(request))
                .requestUri(URLUtil.getPath(request.getRequestURI())).method(request.getMethod())
                .userAgent(request.getHeader("user-agent")).params(HttpUtil.toParams(request.getParameterMap()))
                .clientId(Objects.nonNull(sysOperator)?sysOperator.getId().toString():null)
//                .processId(obtainProcessId(sysLog, request))
                .time(sw.getTotalTimeMillis())
                .body(body)
                .createUser(Objects.nonNull(sysOperator)?sysOperator.getId().toString():null)
                .createUserName(Objects.nonNull(sysOperator)?sysOperator.getOperatorName():null)
                .customerName(Objects.nonNull(sysOperator)?sysOperator.getDeptName():null)
                .createTime(new Date())
                .moduleName(module)
                .role(Objects.nonNull(sysOperator)?sysOperator.getGroupName():null)
                .returnContent(Objects.nonNull(obj)?obj.toString():null);

        sysLogRepository.save(builder.build());
        RequestContextHolder.setRequestAttributes(RequestContextHolder.currentRequestAttributes(), true);
        return obj;
        }
        catch (Exception e){
            log.error("日志记录失败", e);

        }
        return obj;

    }


    @SneakyThrows
    @SuppressWarnings("unchecked")
    private String obtainProcessId(SysOperaLog sysLog, HttpServletRequest request) {

        String id = "";

        switch (sysLog.idLocation()) {
            case path:
                Map<String, String> uriTemplateVars = (Map<String, String>) request.getAttribute(HandlerMapping.URI_TEMPLATE_VARIABLES_ATTRIBUTE);
                if (!CollectionUtils.isEmpty(uriTemplateVars)) {
                    id = uriTemplateVars.get(sysLog.id());
                }
                break;
            case param:
                id = request.getParameter(sysLog.id());
                break;
            case body:
                String body = ServletUtil.getBody(request);

                if (!StringUtils.isEmpty(body)) {

                    JsonNode jsonNode = objectMapper.readTree(body).get(sysLog.id());
                    id = Optional.ofNullable(jsonNode).map(JsonNode::asText).orElse("");
                }
                break;
        }

        return id;
    }
}