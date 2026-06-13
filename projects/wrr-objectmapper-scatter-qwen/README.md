# wrr-objectmapper-scatter

## Question ID: l1-144

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

项目中有16处以上通过 new ObjectMapper() 创建了各自独立的 Jackson ObjectMapper 实例，分布在 RedisSessionConfig、SysOperaLogAspect、TokenInterceptor、JwtUtil、WorkflowProcessor、EnhancedWorkflowProcessor、TextinService、LocationMatching、WordReportGenerator、MultiTableProcessor、TaskReportGenerator 等类中。TasksServiceImpl 的 getTasksDetail 方法甚至在方法体内部（422行和447行）每次调用都 new 两个 ObjectMapper 来解析 referenceDocId 和 selectedItems 的JSON数组字段。这些实例各自独立配置，导致不同模块的JSON序列化行为不一致（比如某些实例忽略未知属性而另一些会抛异常），而且 ObjectMapper 的构造涉及反射扫描开销较大。需要统一 ObjectMapper 的使用方式。
