package com.linkyoyo.reportaudit.security;

import cn.hutool.json.JSONObject;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.linkyoyo.reportaudit.entity.QSysOperator;
import com.linkyoyo.reportaudit.entity.SysOperator;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.SignatureAlgorithm;

import java.util.Date;
import java.util.HashMap;
import java.util.Map;

public class JwtUtil {

    private static final String SECRET_KEY = "Hn-tsp-2024";
    private static final long EXPIRATION_TIME = 3600000*24; // 1 hour
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    public static String generateToken(SysOperator sysOperator) {

        long nowMillis = System.currentTimeMillis();
        Date now = new Date(nowMillis);
        // 添加claims
        Map<String, Object> claims = new HashMap<>();
        claims.put("sysUser",  sysOperator);

        // 生成token
        String token = Jwts.builder()
                .setClaims(claims)
                .setSubject(sysOperator.getId().toString())
                .setIssuedAt(now)
                .signWith(SignatureAlgorithm.HS256, SECRET_KEY)
                .setExpiration(new Date(System.currentTimeMillis() + EXPIRATION_TIME))
                .compact();
        return token;

    }

    public static String validateToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .setSigningKey(SECRET_KEY)
                    .parseClaimsJws(token)
                    .getBody();


            // 将LinkedHashMap转换为JSON字符串
            String json = OBJECT_MAPPER.writeValueAsString(claims.get("sysUser"));
            JSONObject  jsonObject = new JSONObject();
            jsonObject.put("userId",claims.getSubject());
            jsonObject.put("sysUser",json) ;
            if (isTokenExpired(token)){
                jsonObject.put("tokenExpired",true);

//                jsonObject.put("refreshToken",refreshToken(jsonObject.toString())")
            }
            else
            {
                jsonObject.put("tokenExpired",false);
            }
            return jsonObject.toString();

//            return !isTokenExpired(token); // token验证通过及有效期
        } catch (Exception e) {
            return ""; // token验证失败
        }
    }


    public static boolean validateToken(String token, String username) {
        String userNameFromToken = Jwts.parser()
                .setSigningKey(SECRET_KEY)
                .parseClaimsJws(token)
                .getBody()
                .getSubject();

        return (userNameFromToken.equals(username) && !isTokenExpired(token));
    }

    private static boolean isTokenExpired(String token) {
        Date expiration = Jwts.parser()
                .setSigningKey(SECRET_KEY)
                .parseClaimsJws(token)
                .getBody()
                .getExpiration();

        return expiration.before(new Date());
    }
}