package com.linkyoyo.reportaudit.controller;

import org.springframework.web.bind.annotation.*;
import okhttp3.*;
import java.io.IOException;

@RestController
@RequestMapping("/api/ai")
public class AiController {
    private static final String AZURE_ENDPOINT = "https://xxx.openai.azure.com";
    private static final String DEEPSEEK_ENDPOINT = "https://api.deepseek.com";

    @PostMapping("/chat")
    public String chat(@RequestBody String prompt, @RequestParam String provider) throws IOException {
        OkHttpClient client = new OkHttpClient();
        String url = "azure".equals(provider) ? AZURE_ENDPOINT : DEEPSEEK_ENDPOINT;
        Request req = new Request.Builder().url(url).post(RequestBody.create(prompt, MediaType.parse("application/json"))).build();
        try (Response resp = client.newCall(req).execute()) {
            return resp.body().string();
        }
    }
}
