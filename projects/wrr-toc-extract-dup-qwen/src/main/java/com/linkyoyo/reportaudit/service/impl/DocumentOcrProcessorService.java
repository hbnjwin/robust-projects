package com.linkyoyo.reportaudit.service.impl;

import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.repository.DocumentsRepository;
import com.linkyoyo.reportaudit.service.TextinService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 文档OCR处理服务
 * 专门处理异步OCR任务
 */
@Service
public class DocumentOcrProcessorService {

    @Autowired
    private DocumentsRepository documentsRepository;

    @Autowired
    private TextinService textinService;

    @Autowired
    private ExtractionSharedService extractionSharedService;

    /**
     * 异步处理OCR和后续操作
     *
     * @param originalFile 原始文件
     * @param documentId 文档ID
     * @param currentUser 当前用户信息
     */
    @Async
    public void processOcrAsync(java.io.File originalFile, Integer documentId, com.linkyoyo.reportaudit.entity.SysOperator currentUser) {
        System.out.println("开始异步OCR处理，文档ID: " + documentId);

        try {
            // 重新查询文档对象，确保获取最新状态
            Documents document = documentsRepository.findById(documentId).orElse(null);
            if (document == null) {
                System.err.println("异步OCR处理失败：找不到文档ID " + documentId);
                return;
            }

            System.out.println("执行OCR处理...");
            // 执行OCR处理
            textinService.uploadBySysParasetOcr(originalFile, document);

            // 处理Markdown内容的章节整理
            String mdContent = document.getMdContent();
            if (mdContent != null && !mdContent.trim().isEmpty()) {
                try {
                    System.out.println("处理Markdown内容和章节整理...");
                    // 调用章节处理方法
                    Map<String, Object> processResult = com.linkyoyo.reportaudit.util.ProcessRealFile.processMarkdownContent(mdContent);

                    // 更新处理后的Markdown内容
                    String cleanedMarkdown = (String) processResult.get("cleanedMarkdown");
                    if (cleanedMarkdown != null) {
                        document.setMdContent(cleanedMarkdown);
                    }

                    // 处理TOC数据并保存到DocumentsToc表
                    @SuppressWarnings("unchecked")
                    List<Map<String, Object>> tocList = (List<Map<String, Object>>) processResult.get("tableOfContents");
                    if (tocList != null && !tocList.isEmpty()) {
                        extractionSharedService.processTocData(document.getId().intValue(), tocList);
                    }

                } catch (Exception e) {
                    System.err.println("章节处理失败: " + e.getMessage());
                    e.printStackTrace();
                }
            }

            // 更新处理状态为OCR_COMPLETED，并保存mdContent
            document.setProcessingStatus("OCR_COMPLETED");
            document.setUpdatedAt(java.time.LocalDateTime.now());
            documentsRepository.save(document);

            System.out.println("创建抽取任务...");
            // 增加创建extractionTasks的方法
            extractionSharedService.createExtractionTasks(document.getId().longValue(), currentUser);

            System.out.println("异步OCR处理完成，文档ID: " + documentId);

        } catch (Exception e) {
            System.err.println("异步OCR处理失败，文档ID: " + documentId + ", 错误: " + e.getMessage());
            e.printStackTrace();

            // 更新处理状态为OCR_FAILED
            try {
                Documents document = documentsRepository.findById(documentId).orElse(null);
                if (document != null) {
                    document.setProcessingStatus("OCR_FAILED");
                    document.setProcessingError(e.getMessage());
                    document.setUpdatedAt(java.time.LocalDateTime.now());
                    documentsRepository.save(document);
                }
            } catch (Exception saveException) {
                System.err.println("保存OCR失败状态时出错: " + saveException.getMessage());
            }
        }
    }
}
