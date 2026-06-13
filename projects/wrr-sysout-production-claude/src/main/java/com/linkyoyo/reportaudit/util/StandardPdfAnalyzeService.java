package com.linkyoyo.reportaudit.util;

import cn.hutool.core.io.FileUtil;
import cn.hutool.core.util.ReUtil;
import cn.hutool.core.util.StrUtil;
import cn.hutool.json.JSONObject;
import cn.hutool.json.JSONArray;
import cn.hutool.json.JSONUtil;

import com.azure.ai.openai.OpenAIClient;
import com.azure.ai.openai.OpenAIClientBuilder;
import com.azure.ai.openai.OpenAIServiceVersion;
import com.azure.ai.openai.models.*;
import com.azure.core.credential.AzureKeyCredential;
import com.linkyoyo.reportaudit.entity.QSysParaset;
import com.linkyoyo.reportaudit.entity.SysParaset;
import com.linkyoyo.reportaudit.service.TextinService;
import com.linkyoyo.reportaudit.support.CommonFunc;
import com.querydsl.jpa.impl.JPAQueryFactory;
import io.micrometer.core.instrument.util.StringUtils;
import lombok.extern.slf4j.Slf4j;
import net.sourceforge.tess4j.Tesseract;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.poi.hwpf.HWPFDocument;
import org.apache.poi.hwpf.extractor.WordExtractor;
import org.apache.poi.poifs.filesystem.POIFSFileSystem;
import org.apache.poi.xwpf.usermodel.XWPFDocument;
import org.apache.poi.xwpf.usermodel.XWPFParagraph;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.multipart.MultipartFile;

import javax.imageio.ImageIO;
import javax.persistence.EntityManager;
import java.awt.image.BufferedImage;
import java.io.*;
import java.util.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Arrays;

//import com.itextpdf.text.pdf.PdfReader;
//import com.itextpdf.text.pdf.parser.PdfTextExtractor;


@Component
@Slf4j
public class StandardPdfAnalyzeService implements InitializingBean {
    @Autowired
    private JPAQueryFactory jpaQueryFactory;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private TextinService textinService;

    private static final String ACCOUNT_NUMBER_BRF = "Account Number";

    private static final String CHINA_ACCOUNT_NUMBER_BRF = "Account Number:";

    private final static Integer FIRST_PAGE = 1;

    private final static Integer SUPPLIER_INDEX = 0;


    private String pdfLineBreak;

    @Value("${paraSet.uploadPath}")
    private String dataPath;


    public String findStandardName(List<String> lstContent, Integer beginIdx) {
        for (int i = beginIdx + 1; i < lstContent.size(); i++) {

            if (lstContent.get(i).trim().length() > 1)
                if (lstContent.get(i).trim().charAt(0) >= 0x4e00 && lstContent.get(i).trim().charAt(0) <= 0x9fa5) {
                    //去除 代开头的
                    if (lstContent.get(i).trim().startsWith("代"))
                        continue;


                    if ((i + 1) < lstContent.size()) {
                        if (lstContent.get(i + 1).trim().length() > 1)
                            if (lstContent.get(i + 1).trim().charAt(0) >= 0x4e00 && lstContent.get(i + 1).trim().charAt(0) <= 0x9fa5)
                                return lstContent.get(i).trim() + " " + lstContent.get(i + 1).trim();
                            else
                                return lstContent.get(i).trim();
                    }
                    return lstContent.get(i).trim();
                }

        }
        return "";

    }


    public Boolean judgeContainNumber(String content) {
        return ReUtil.isMatch(".*[0-9].*", content);
    }

    public Integer findStandardNoBeginIdx(List<String> lstContent, String prefix, String standardType) {
        for (int i = 0; i < lstContent.size(); i++) {
            String[] arr = prefix.trim().split(",");
            for (int j = 0; j < (arr.length); j++) {

                if (StrUtil.startWith(lstContent.get(i).trim(), arr[j])) {
                    if (judgeContainNumber(lstContent.get(i).trim())) {
//                 standardType = prefix.equals("GBPrefix")?"GB":prefix.equals("HBPrefix")? "YC": prefix.equals("QBPrefix")? "HNYQ": "";
                        return i;
                    }
                }
            }
        }
        return -1;

    }

    public JSONObject findStandardNo(List<String> lstContent) {
        QSysParaset qSysParaset = QSysParaset.sysParaset;
        CommonFunc.clearEntityManager(entityManager);
        SysParaset sysParaset = jpaQueryFactory.select(qSysParaset).from(qSysParaset).fetchFirst();

        JSONObject jsonObject = JSONUtil.parseObj(sysParaset.getFileTitleFormat());
        String GBPrefix = jsonObject.getStr("GBPrefix");
        String HBPrefix = jsonObject.getStr("HBPrefix");
        String QBPrefix = jsonObject.getStr("QBPrefix");
        Integer idx = -1;
        String standardType = "";
        idx = findStandardNoBeginIdx(lstContent, GBPrefix, standardType);

        if (idx == -1) {
            idx = findStandardNoBeginIdx(lstContent, HBPrefix, standardType);

            if (idx == -1) {
                idx = findStandardNoBeginIdx(lstContent, QBPrefix, standardType);
                if (idx != -1)
                    standardType = "HNYQ";
            } else
                standardType = "YC";
        } else
            standardType = "GB";


        JSONObject result = new JSONObject();
        if (idx != -1) {
            result.putOnce("standardLevelName", standardType);
            result.putOnce("standardNo", lstContent.get(idx).trim());
            //从标准号之后寻找标准名称
            String standardName = findStandardName(lstContent, idx);
            if (!standardName.equals(""))
                result.putOnce("standardName", standardName);

        }

        //搜索发布单位
        for (int i = 0; i < lstContent.size(); i++) {
            if (lstContent.get(i).trim().length() > 1)
                if (lstContent.get(i).trim().charAt(0) >= 0x4e00 && lstContent.get(i).trim().charAt(0) <= 0x9fa5) {
                    if (lstContent.get(i).trim().contains("发 布")) {
                        result.putOnce("publishUnit", CommonFunc.getString("@@" + lstContent.get(i).trim(), "@@", "发 布"));
                        break;
                    }

                    if (lstContent.get(i).trim().contains("发布")) {
                        result.putOnce("publishUnit", CommonFunc.getString("@@" + lstContent.get(i).trim(), "@@", "发布"));
                        break;
                    }

                }
        }

        //搜素发布时间  StrUtil.startWith(lstContent.get(i).trim(), prefix.trim())
        for (int i = 0; i < lstContent.size(); i++) {
            if (StrUtil.startWith(lstContent.get(i).trim(), "20")) {
                if (lstContent.get(i).trim().contains("发布") || lstContent.get(i).trim().contains("发 布")) {

                    result.putOnce("publishDate", CommonFunc.getString("@@" + lstContent.get(i).trim(), "@@", "发").replace(" ", "")
                            .replace("–", "-")
                            .toLowerCase().replace("xx", "01"));
                    break;
                }

            }
        }

        return result;

    }


    public JSONObject analyzeByOpenAi() {
//        https://bluecloud-bca-ai.openai.azure.com/openai/deployments/gpt-4o-mini/chat/completions/
//        OpenAIClient  buildClient

        OpenAIClient client = new OpenAIClientBuilder()
                .credential(new AzureKeyCredential("REDACTED_AZURE_KEY"))
                .endpoint("https://bluecloud-bca-ai.openai.azure.com/")   //https://bluecloud-bca-ai.openai.azure.com/openai/deployments/
                .serviceVersion(OpenAIServiceVersion.V2024_05_01_PREVIEW)
                .buildClient();

//        List<ChatMessageImageUrl> chatMessages = new ArrayList<>();
        List<ChatRequestMessage> chatMessages = new ArrayList<>();


        chatMessages.add(new ChatRequestUserMessage(Arrays.asList(
                new ChatMessageTextContentItem("分析这张图片，用key,value格式输出，解析内容:标准编号，标题，发布日期，发布单位"),
                new ChatMessageImageContentItem(
                        new ChatMessageImageUrl("D:\\work\\河南烟草\\pdf解析\\0903.png"))
        )));

          /*  List<ChatRequestMessage> chatMessages = new ArrayList<>();
        chatMessages.add(new ChatRequestSystemMessage( "You are a helpful assistant. You will talk like a pirate."));
        chatMessages.add(new ChatRequestUserMessage( "采用delphi写一个冒泡算法"));*/

        /*List<ChatMessage> chatMessages = new ArrayList<>();

        chatMessages.add(new ChatMessage(ChatRole.SYSTEM, "Of course, me hearty! What can I do for ye?"));
        chatMessages.add(new ChatMessage(ChatRole.USER, "What's the best way to train a parrot?"));*/


        ChatCompletions chatCompletions = client.getChatCompletions("gpt-4o-mini", new ChatCompletionsOptions(chatMessages));

        System.out.printf("Model ID=%s is created at %s.%n", chatCompletions.getId(), chatCompletions.getCreatedAt());
        for (ChatChoice choice : chatCompletions.getChoices()) {
            ChatResponseMessage message = choice.getMessage();
            System.out.printf("Index: %d, Chat Role: %s.%n", choice.getIndex(), message.getRole());
            System.out.println("Message:");
            System.out.println(message.getContent());
        }



        /*IterableStream<ChatCompletions> chatCompletionsStream = client.getChatCompletionsStream("gpt-4o-mini",
                new ChatCompletionsOptions(chatMessages));

        chatCompletionsStream
                .stream()
                // Remove .skip(1) when using Non-Azure OpenAI API
                // Note: the first chat completions can be ignored when using Azure OpenAI service which is a known service bug.
                // TODO: remove .skip(1) when service fix the issue.
                .skip(1)
                .forEach(chatCompletions -> {
                    ChatResponseMessage delta = chatCompletions.getChoices().get(0).getDelta();
                    if (delta.getRole() != null) {
                        System.out.println("Role = " + delta.getRole());
                    }
                    if (delta.getContent() != null) {
                        System.out.print(delta.getContent());
                    }
                });*/
        return null;

    }


    private void removeError(List<String> lineList) {
        lineList.removeIf(StringUtils::isBlank);
        if (lineList.size() == 0)
            return;

        for (int idx = 0; idx <= lineList.size() - 1; idx++) {
            if (lineList.get(idx).trim().charAt(0) >= 0x4e00 && lineList.get(idx).trim().charAt(0) <= 0x9fa5)
                break;

            if (Character.isLetter(lineList.get(idx).trim().charAt(0)) && judgeContainNumber(lineList.get(idx).trim()))
                lineList.set(idx, "");
        }

        lineList.removeIf(StringUtils::isBlank);

    }

    public JSONObject analyze(File pdf, Boolean useOCR, Boolean useLlm, Integer dpi, SysParaset sysParaset) {
        try {


            String extName = FileUtil.extName(pdf);

            if (extName.toLowerCase().equals("doc") || extName.toLowerCase().equals("docx")) {
                List<String> lineList = new ArrayList<>();
                if (extName.equals("docx")) {

                    try {
                        log.info("开始解析docx文件：{}", pdf.getAbsolutePath());
                        XWPFDocument document = new XWPFDocument(new FileInputStream(pdf.getAbsolutePath()));
                        for (XWPFParagraph paragraph : document.getParagraphs()) {
                            String text = paragraph.getText();
                            text = text.replace("\n", "").replace("\r", "")
                                    .replace("\b", "").replace("\f", "").trim();
                            if (StrUtil.isNotEmpty(text))
                                lineList.add(text);
                            if (lineList.size() >= 12)
                                break;
                        }

                        // 关闭文档
                        document.close();
                        log.info("docx解析完成：{}", lineList);
                    } catch (Exception e) {
                        log.error("转换错误:", e.getMessage());

                    }
                } else {

                    try {
                        log.info("开始解析doc文件：{}", pdf.getAbsolutePath());

                        HWPFDocument document = new HWPFDocument(new POIFSFileSystem(new FileInputStream(pdf.getAbsolutePath())));
                        WordExtractor extractor = new WordExtractor(document);

                        String[] paragraphs = extractor.getParagraphText();
                        for (String text : paragraphs) {
                            text = text.replace("\n", "").replace("\r", "")
                                    .replace("\b", "").replace("\f", "").trim();
                            if (StrUtil.isNotEmpty(text))
                                lineList.add(text);

                            if (lineList.size() >= 12)
                                break;
                        }
                        // 关闭文档
                        document.close();
                        log.info("doc解析完成：{}", lineList);

                    } catch (Exception e) {
                        log.error("转换错误:", e.getMessage());

                    }

                }


//                if (lineList.size() > 0 && judgeContainNumber(lineList.get(0).trim())) // lineList.get(0).contains("##"))
//                    lineList.remove(0);
                removeError(lineList);

                JSONObject obj = findStandardNo(lineList);

                if (Objects.nonNull(obj) && obj.size() >= 2) {
                    if (obj.containsKey("standardLevelName") && obj.get("standardLevelName").toString().equals("HNYQ")
                            && obj.containsKey("standardNo")) {

                        String newYQ = "";
                        if (obj.get("standardNo").toString().trim().startsWith("YQ"))
                            newYQ = "YQ";
                        else
                            newYQ = obj.get("standardNo").toString().trim().substring(2, 6);
//                            CommonFunc.getString(obj.get("standardNo").toString(),"Q/"," ");
                        if (StrUtil.isNotEmpty(newYQ))
                            obj.set("standardLevelName", newYQ);

                    }
                }


                return obj;


            }


            if (extName.toLowerCase().equals("pdf")) {
                log.info("开始解析PDF文件");

                // 检查是否启用了Agent功能
                if (sysParaset.getUseAgent() != null && sysParaset.getUseAgent()) {
                    log.info("使用Agent功能解析PDF文件: {}", pdf.getAbsolutePath());
                    try {
                        // 获取当前路径
                        String currentPath = pdf.getParent();
                        log.info("当前文件路径: {}", currentPath);

                        // 直接使用File版本的uploadByBlueCloudAi方法
                        // 这将使用当前路径保存Markdown文件
                        String documentId = textinService.uploadByBlueCloudAi(pdf);
                        String fileName = pdf.getName();
                        log.info("文档已上传并转换为Markdown，文档ID: {}", documentId);

                        // 获取Markdown文件路径
                        String baseName = fileName;
                        if (baseName.contains(".")) {
                            baseName = baseName.substring(0, baseName.lastIndexOf('.'));
                        }
                        String mdFilePath = currentPath + File.separator + baseName + ".md";
                        log.info("Markdown文件路径: {}", mdFilePath);
                        //读取md 内容
                        /*String markdownContent = "";
                        if (FileUtil.exist(mdFilePath)) {
                            markdownContent = FileUtil.readUtf8String(mdFilePath);
                            log.info("成功读取Markdown文件内容，文件大小: {} 字节", markdownContent.length());
                        } else {
                            log.warn("找不到Markdown文件，无法读取内容: {}", mdFilePath);
                        }*/

                        // 提取目录结构并格式化 markdownContent
                        List<MarkdownFormatterUtil.TocEntry> tocEntries = new ArrayList<>() ;

                        JSONObject resultObj = new JSONObject();
                        JSONArray tocArray = new JSONArray();

                        // 1. 整理md文件，使用MarkdownFormatterUtil格式化并保存
                        // 2. 创建简化版md文件，去掉图片base64串和表格
                        // 读取简化版的md文件内容
                        String simpleMdPath = currentPath + File.separator + baseName + "_simple.md";
                        if (FileUtil.exist(mdFilePath)) {
                            log.info("开始处理Markdown文件: {}", mdFilePath);
                            boolean success = MarkdownCleanupUtil.processMarkdownFile(mdFilePath);

                            /// 处理目录
                            String markdownContent = "";
                            if (FileUtil.exist(simpleMdPath)) {
                                markdownContent = FileUtil.readUtf8String(simpleMdPath);
                                log.info("成功读取Markdown文件内容，文件大小: {} 字节", markdownContent.length());
                            } else {
                                log.warn("找不到Markdown文件，无法读取内容: {}", simpleMdPath);
                            }

                            // 提取目录结构并格式化 markdownContent
                             tocEntries = MarkdownFormatterUtil.extractTableOfContents(markdownContent);
                            log.info("成功提取目录结构，共 {} 个条目", tocEntries.size());
                            // 创建JSONObject存储目录结构


                            // 将TocEntry列表转换为JSONArray
                            for (MarkdownFormatterUtil.TocEntry entry : tocEntries) {
                                JSONObject entryObj = new JSONObject();
                                entryObj.set("title", entry.getTitle());
                                entryObj.set("number", entry.getNumber());
                                entryObj.set("level", entry.getLevel());
                                entryObj.set("lineNumber", entry.getLineNumber());
                                entryObj.set("type", entry.getType());
                                entryObj.set("originalLine", entry.getOriginalLine());
                                tocArray.add(entryObj);
                            }

                            // 保存 到JSONObject "standardDocTocList" ：tocEntries ，最终和下面 简化版解析内容合并一起返回
                            resultObj.set("standardDocTocList", tocArray);
                           /// 处理目录



                            if (success) {
                                log.info("Markdown文件处理成功");
                            } else {
                                log.error("Markdown文件处理失败");
                            }
                        } else {
                            log.warn("找不到Markdown文件: {}", mdFilePath);
                        }
                        // 3. 使用Ai分析Markdown文件，返回JSONObject
                        // 读取简化版的md文件内容
//                        String simpleMdPath = currentPath + File.separator + baseName + "_simple.md";
                        if (FileUtil.exist(simpleMdPath)) {
                            log.info("开始处理简化版Markdown文件: {}", simpleMdPath);
                            try {
                                String content = FileUtil.readUtf8String(simpleMdPath);
                                JSONObject result = processSimpleMdContent(content);
                                // 存储Markdown文件路径
                                result.set("mdFilePath", new File(mdFilePath).getName());
                                result.set("simpleMdFilePath", new File(simpleMdPath).getName());

                                // 将目录结构合并到结果中
                                if (resultObj.containsKey("standardDocTocList")) {
                                    result.set("standardDocTocList", resultObj.get("standardDocTocList"));
                                    log.info("成功将目录结构合并到结果中，目录条目数量: {}", tocEntries.size());
                                }

                                return result;
                            } catch (Exception e) {
                                log.error("处理简化版Markdown文件失败: {}", e.getMessage(), e);
                            }
                        } else {
                            log.warn("找不到简化版Markdown文件: {}", simpleMdPath);
                        }
                        return null;

                        // 返回标准信息
//                        JSONObject obj = findStandardNo(Arrays.asList(fileName.split("\\\\")));
//                        return obj;
                    } catch (Exception e) {
                        log.error("使用Agent功能解析PDF文件失败: {}", e.getMessage(), e);
                        // 如果Agent处理失败，继续使用原有方法
                    }
                }

                PDDocument pdDocument = Loader.loadPDF(pdf);

                List<String> lineList = new ArrayList<>();
                JSONObject obj = null;

                if (!sysParaset.getAllAi()) {
                    PDFTextStripper pdfTextStripper = new PDFTextStripper();

                    pdfTextStripper.setSortByPosition(true);
                    pdfTextStripper.setStartPage(FIRST_PAGE);
                    pdfTextStripper.setEndPage(FIRST_PAGE);
                    String text = pdfTextStripper.getText(pdDocument);
                    log.info("pdf 解析结果:{}", text);

                    lineList = StrUtil.split(text, pdfLineBreak);
//                if (lineList.size() > 0 && judgeContainNumber(lineList.get(0).trim())) // lineList.get(0).contains("##"))
//                    lineList.remove(0);

                    removeError(lineList);

                    obj = findStandardNo(lineList);

                    if (Objects.nonNull(obj) && obj.size() >= 2) {
                        if (obj.containsKey("standardLevelName") && obj.get("standardLevelName").toString().equals("HNYQ")
                                && obj.containsKey("standardNo")) {

                            String newYQ = "";
                            if (obj.get("standardNo").toString().trim().startsWith("YQ"))
                                newYQ = "YQ";
                            else {

                                if (obj.get("standardNo").toString().trim().contains(" "))
                                    newYQ = CommonFunc.getString(obj.get("standardNo").toString(), "Q/", " ");
                                else {
                                    newYQ = obj.get("standardNo").toString().trim().substring(2, 6);
                                }
                                newYQ = "Q/" + newYQ;
                            }
//                                obj.get("standardNo").toString().trim().substring(2, 6);
//                            CommonFunc.getString(obj.get("standardNo").toString(),"Q/"," ");
                            if (StrUtil.isNotEmpty(newYQ))
                                obj.set("standardLevelName",  newYQ);

                        }
                    }
                }

                if ((useOCR || useLlm) &&
                        (Objects.isNull(obj) || (Objects.nonNull(obj) && obj.size() >= 0 && !obj.containsKey("standardNo")))) {

                    //  将第一页转换为图像
                    PDFRenderer renderer = new PDFRenderer(pdDocument);
                    BufferedImage image = renderer.renderImageWithDPI(0, dpi); // 设置图像分辨率为70 DPI
                    log.info("图像大小:{}", image.getWidth() + "x" + image.getHeight());

                    if (useLlm) {
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        ImageIO.write(image, "png", baos); // 可以改为需要的图片格式，如"jpg"
                        byte[] imageBytes = baos.toByteArray();
//                        lineList = CommonFunc.callOpenAi(Base64.getEncoder().encodeToString(imageBytes));
                        //standardLevelName ,standardNo,publishDate,publishUnit,standardLevelName
//                        obj = findStandardNo(lineList);
                        try {
//                            CommonFunc.createTempFile(imageBytes,"tmp"+System.currentTimeMillis(),"png");
                            return CommonFunc.callAi(CommonFunc.createTempFile(imageBytes, "tmp" + System.currentTimeMillis(), ".png"));
                        } catch (Exception e) {
                            log.error("ai 解析错误:{}", e.getMessage());
                        }
                        return null;
//                        return CommonFunc.callNewOpenAi(Base64.getEncoder().encodeToString(imageBytes));
                    } else {


                        try {

                            //  使用OCR识别图像中的文字
                            Tesseract tesseract = new Tesseract();
                            log.info("训练库位置：{}", dataPath + File.separator + "tessdata");
                            tesseract.setDatapath(dataPath + File.separator + "tessdata"); // 设置Tesseract的语言数据文件路径; /usr/share/tesseract-ocr/4.00/tessdata
                            log.info("设置tesseract.setDatapath训练库位置完成");
                            tesseract.setLanguage("chi_sim");
                            log.info("设置语言类型tesseract.setLanguage(\"chi_sim\")");
                            StringBuilder result = new StringBuilder();
                            String ocrText = tesseract.doOCR(image);
                            log.info("{} OCR识别结果：{}", pdf.getAbsolutePath(), ocrText);

                            lineList = StrUtil.split(ocrText, "\n");

                            obj = findStandardNo(lineList);
                            return obj;

                        } catch (Exception e) {
                            log.error("OCR识别失败，请检查文件格式{}", e.getMessage());
                        }
                    }
                }


                return obj;
            }
        } catch (Exception e) {
            log.error("pdf文件解析失败，请检查文件格式{}", pdf.getAbsolutePath());
        }
        return null;

    }

    public JSONObject analyze(MultipartFile pdf) throws IOException {
        PDDocument pdDocument = Loader.loadPDF(pdf.getBytes());
        PDFTextStripper pdfTextStripper = new PDFTextStripper();
        pdfTextStripper.setSortByPosition(true);
        pdfTextStripper.setStartPage(FIRST_PAGE);
        pdfTextStripper.setEndPage(FIRST_PAGE);
        String text = pdfTextStripper.getText(pdDocument);


        List<String> lineList = StrUtil.split(text, pdfLineBreak);

        String supplierPdfName = lineList.get(SUPPLIER_INDEX);
        JSONObject obj = findStandardNo(lineList);

        return obj;
    }


    /**
     * 处理简化版Markdown内容，根据配置调用不同的AI服务进行分析
     * @param content Markdown内容
     * @return 解析结果
     */
    private JSONObject processSimpleMdContent(String content) {
        log.info("处理简化版Markdown内容");

        // 删除控制字符
        content = content.replaceAll("[\\p{Cntrl}&&[^\\r\\n\\t]]", "");
        // 转义反斜杠和引号
        content = content.replace("\\", "\\\\").replace("\"", "\\\"");

        log.info("处理后的内容长度: {}", content.length());

        // 根据aiType选择不同的AI调用方法
        JSONObject result;
        if (CommonFunc.linkyoyoAiConfig != null) {
            Integer aiType = CommonFunc.linkyoyoAiConfig.getAiType();
            log.info("使用AI类型: {}", aiType);

            switch (aiType) {
                case 1:
                    log.info("使用callAiWithOkHttp方法");
                    result = CommonFunc.callAiWithOkHttp(content);
                    break;
                case 2:
                    log.info("使用callDeepSeekAi方法");
                    result = CommonFunc.callDeepSeekAi(content);
                    break;
                case 0:
                default:
                    log.info("使用默认callAi方法");
                    result = CommonFunc.callAi(content);
                    break;
            }
        } else {
            log.info("LinkyoyoAiConfig未配置，使用默认callAi方法");
            result = CommonFunc.callAi(content);
        }

        if (result.containsKey("error")) {
            log.error("调用AI服务失败: {}", result.getStr("error"));
            return new JSONObject();
        }

        // 将Hutool JSONObject转换为Java Map对象，解决序列化问题
        Map<String, Object> resultMap = new HashMap<>();
        for (String key : result.keySet()) {
            Object value = result.get(key);
            // 处理JSONNull类型
            if (value instanceof cn.hutool.json.JSONNull) {
                resultMap.put(key, null);
            } else {
                resultMap.put(key, value);
            }
        }

        // 创建新的JSONObject用于返回
        JSONObject standardInfo = new JSONObject();

        // 映射字段
        if (resultMap.containsKey("标准号")) {
            standardInfo.set("standardNo", resultMap.get("标准号"));
        }
        if (resultMap.containsKey("标准中文名")) {
            standardInfo.set("standardName", resultMap.get("标准中文名"));
        }
        if (resultMap.containsKey("发布日期")) {
            standardInfo.set("publishDate", resultMap.get("发布日期"));
        }
        if (resultMap.containsKey("发布单位")) {
            standardInfo.set("publishUnit", resultMap.get("发布单位"));
        }
        if (resultMap.containsKey("标准类型")) {
            standardInfo.set("standardLevelName", resultMap.get("标准类型"));
        }
        if (resultMap.containsKey("标准状态")) {
            standardInfo.set("standardStatus", resultMap.get("标准状态"));
        }
        if (resultMap.containsKey("实施日期")) {
            standardInfo.set("implementDate", resultMap.get("实施日期"));
        }
        if (resultMap.containsKey("标准英文名")) {
            standardInfo.set("standardEnName", resultMap.get("标准英文名"));
        }
        if (resultMap.containsKey("起草单位")) {
            standardInfo.set("draftUnit", resultMap.get("起草单位"));
        }
        if (resultMap.containsKey("起草人")) {
            standardInfo.set("drafter", resultMap.get("起草人"));
        }
        if (resultMap.containsKey("提出单位")) {
            standardInfo.set("proposeUnit", resultMap.get("提出单位"));
        }
        if (resultMap.containsKey("范围")) {
            standardInfo.set("scope", resultMap.get("范围"));
        }
        if (resultMap.containsKey("引言")) {
            standardInfo.set("introduction", resultMap.get("引言"));
        }
        if (resultMap.containsKey("参考文献")) {
            standardInfo.set("referenceDocs", resultMap.get("参考文献"));
        }
        if (resultMap.containsKey("规范性引用文件")) {
            standardInfo.set("normativeReferences", resultMap.get("规范性引用文件"));
        }
        if (resultMap.containsKey("术语和定义")) {
            standardInfo.set("termsAndDefinitions", resultMap.get("术语和定义"));
        }
        if (resultMap.containsKey("前言")) {
            standardInfo.set("preface", resultMap.get("前言"));
        }

        // 保存原始AI分析结果
        standardInfo.set("aiAnalysisResult", result.toString());

        return standardInfo;
    }

    @Override
    public void afterPropertiesSet() {
        String activeProfile = MySpringUtil.getActiveProfile();
        if (StrUtil.equals(activeProfile, "local")) {
            pdfLineBreak = StrUtil.CRLF;
        } else {
            pdfLineBreak = StrUtil.LF;
        }
    }
}
