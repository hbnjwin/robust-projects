package com.example.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableGlobalMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Spring Security 配置
 *
 * 关键修复：
 * 1. @EnableGlobalMethodSecurity(prePostEnabled = true)
 *    → 启用 @PreAuthorize / @PostAuthorize 注解扫描
 *    → 修复"接口配置了权限注解但没生效"的问题
 * 2. securedEnabled = true 启用 @Secured 注解支持
 */
@Configuration
@EnableWebSecurity
@EnableGlobalMethodSecurity(prePostEnabled = true, securedEnabled = true)
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf().disable()
            .authorizeRequests()
                // 健康检查等公开接口放行
                .antMatchers("/health", "/public/**").permitAll()
                // 其余接口由方法级注解 @PreAuthorize 控制
                .anyRequest().authenticated()
            .and()
            .httpBasic(); // 简单 Basic Auth，生产环境建议替换为 JWT/OAuth2
        return http.build();
    }
}
