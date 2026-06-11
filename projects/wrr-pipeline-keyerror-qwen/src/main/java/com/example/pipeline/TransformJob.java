package com.example.pipeline;

import java.util.*;

public class TransformJob {

    public List<Map<String, Object>> transform(List<Map<String, Object>> records) {
        List<Map<String, Object>> result = new ArrayList<>();
        for (Map<String, Object> record : records) {
            Map<String, Object> out = new HashMap<>();
            out.put("id", record.get("id"));
            out.put("name", record.get("name"));
            // BUG: assumes "amount" always exists and is numeric
            out.put("amount", ((Number) record.get("amount")).doubleValue());
            result.add(out);
        }
        return result;
    }
}
