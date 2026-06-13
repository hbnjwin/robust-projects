package com.linkyoyo.reportaudit.controller;

import com.linkyoyo.reportaudit.annotation.SysOperaLog;
import com.linkyoyo.reportaudit.entity.Documents;
import com.linkyoyo.reportaudit.info.DocumentsInfo;
import com.linkyoyo.reportaudit.query.DocumentsQuery;
import com.linkyoyo.reportaudit.result.R;
import com.linkyoyo.reportaudit.result.CodeMsg;
import com.linkyoyo.reportaudit.service.DocumentsService;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import javax.validation.constraints.NotNull;

@RequestMapping("/documents")
@RestController
public class DocumentsController {
    @Autowired
    private DocumentsService documentsService;

    @GetMapping("/list")
    public R getDocumentsList(DocumentsQuery documentsQuery) {
        return R.ok(documentsService.getDocumentsList(documentsQuery));
    }

    @GetMapping("/listDetail")
    public R getDocumentsDetail(DocumentsInfo documentsInfo) {
        return R.ok(documentsService.getDocumentsDetail(documentsInfo.getId()));
    }

    @PostMapping("/update")
    public R updateData(@RequestBody DocumentsInfo documentsInfo) {
        return R.ok(documentsService.createOrUpdate(documentsInfo));
    }

    @RequestMapping("/delete")
    public R delete(@RequestParam("id") Integer id) {
        if (id == null) {
            return R.warning("id不能为空");
        }
        documentsService.markDeleted(id);
        return R.ok("删除成功");
    }
    
    /**
     * 上传并处理PDF/DOCX文件，使用sys_paraset表中的OCR参数进行转换
     *
     * @param file 上传的PDF/DOCX文件
     * @param docType 文档类型：0-已审核，1-待审核，2-可研报告，默认值为0
     * @return 转换后的文档ID
     */
    @PostMapping("/uploadFile")
    @SysOperaLog(value="上传文档",id="专家文档库")
    public R uploadFile(@NotNull @RequestParam("file") MultipartFile file,
                       @RequestParam(value = "docType", defaultValue = "0") Integer docType) {
        if (file.isEmpty()) {
            return R.warning("上传的文件为空");
        }
        
        // 检查文件类型
        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null) {
            return R.warning("文件名不能为空");
        }
        
        // 支持PDF和DOCX文件
        if (!originalFilename.endsWith(".pdf") && !originalFilename.endsWith(".docx")) {
            return R.warning("只支持上传PDF文件(.pdf)或DOCX文件(.docx)");
        }
        
        try {
            // 使用DocumentsService处理文件上传和OCR转换
            Documents document = documentsService.uploadFileWithOcr(file, docType);
            return R.ok(document);
        } catch (Exception e) {
            return R.error(CodeMsg.FILE_UPLOAD_ERROR.fillArgs(e.getMessage()));
        }
    }
    
    /**
     * 重新生成文档的目录结构
     * 根据文档的mdContent内容，删除旧的documents_toc记录，重新生成目录结构
     *
     * @param docId 文档ID
     * @return 操作结果
     */
    @PostMapping("/regenerateToc")
    public R regenerateToc(@RequestParam("docId") Integer docId) {
        try {
            Documents document = documentsService.regenerateToc(docId);
            return R.ok(document);
        } catch (Exception e) {
            e.printStackTrace();
            return R.error("重新生成目录失败: " + e.getMessage());
        }
    }
}
