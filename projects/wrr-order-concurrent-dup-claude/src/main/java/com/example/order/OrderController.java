package com.example.order;

import org.springframework.web.bind.annotation.*;
import java.util.*;
import java.util.concurrent.*;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final Map<String, Object> cache = new ConcurrentHashMap<>();
    private int currentPage = 1;  // BUG: shared mutable state
    private int pageSize = 10;

    @GetMapping
    public Map<String, Object> listOrders(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        // BUG: currentPage is shared across concurrent requests
        this.currentPage = page;
        this.pageSize = size;
        Map<String, Object> result = new HashMap<>();
        result.put("page", currentPage);
        result.put("size", pageSize);
        return result;
    }
}
