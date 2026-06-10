package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.PromptTemplates;
import org.mvel2.MVEL;
import org.springframework.stereotype.Service;
import java.util.*;

@Service
public class PromptExecutionServiceImpl {
    public String renderPrompt(PromptTemplates template, String documentContent) {
        Map<String, Object> vars = new HashMap<>();
        vars.put("documentContent", documentContent);
        return (String) MVEL.eval(template.getContent(), vars);
    }
}
