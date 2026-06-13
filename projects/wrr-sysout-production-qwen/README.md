# wrr-sysout-production

## Question ID: l1-145

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

DocumentOcrProcessorService 类中有11处使用 System.out.println 和 System.err.println 输出调试信息（如OCR转换进度、任务创建结果），但该类并未使用 @Slf4j 注解。DocumentsServiceImpl 的 createExtractionTasks 方法中有6处 System.out.println。StandardPdfAnalyzeService 有5处。ProcessRealFile 类几乎全程使用 System.out.println 来输出文件处理过程（约30处）。LinkyoyoAgentConfig 的配置加载也用了3处 System.out。此外有21处 e.printStackTrace() 分布在 DocumentsController、DocumentsServiceImpl、DocumentOcrProcessorService、CommonFunc、WordReportGenerator、MarkdownProcessor、MultiImageProcessor 等类中。这些输出绕过了SLF4J日志框架的级别控制和日志轮转，在容器化部署中输出到stderr的堆栈跟踪无法被日志聚合系统采集。需要将所有 System.out/err 和 e.printStackTrace() 替换为结构化日志。
