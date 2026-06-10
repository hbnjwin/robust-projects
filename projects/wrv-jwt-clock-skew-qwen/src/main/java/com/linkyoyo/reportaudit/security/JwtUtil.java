package com.linkyoyo.reportaudit.security;

import io.jsonwebtoken.*;
import java.util.Date;

public class JwtUtil {
    private static final String SECRET = "reportaudit-secret-key";
    private static final long EXPIRATION = 86400000; // 24h

    public static String generateToken(String username) {
        return Jwts.builder()
            .setSubject(username)
            .setIssuedAt(new Date())
            .setExpiration(new Date(System.currentTimeMillis() + EXPIRATION))
            .signWith(SignatureAlgorithm.HS256, SECRET)
            .compact();
    }

    public static String validateToken(String token) {
        Claims claims = Jwts.parser()
            .setSigningKey(SECRET)
            .parseClaimsJws(token)
            .getBody();
        if (claims.getExpiration().before(new Date())) {
            throw new RuntimeException("Token expired");
        }
        return claims.getSubject();
    }
}
