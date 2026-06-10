package com.linkyoyo.reportaudit.service;

import com.linkyoyo.reportaudit.entity.Documents;

public interface TextinService {
    void processOcr(Documents document);
    String getOcrResult(Long documentId);
}
