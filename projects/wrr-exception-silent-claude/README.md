# wrr-exception-silent

## Question ID: l1-146

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: claude

## Query

SysUserUtils.currentUser() 方法在获取当前登录用户时，catch 块静默吞掉了所有异常并返回一个空的 SysOperator 对象（非null），导致调用方无法区分未登录和会话数据损坏两种情况，使用空用户信息创建的文档和任务记录的 creater、deptId 字段为 null。SysOperaLogAspect 的三个 catch 块也完全吞掉异常不做任何处理，审计日志保存失败时无任何记录。另外整个项目没有定义任何自定义异常类，所有业务错误都使用 RuntimeException 或 generic Exception 抛出，ExtractionTasksServiceImpl 和 CheckResultServiceImpl 在实体未找到时直接返回 null 而非抛出明确异常，全局异常处理器无法区分文档未找到（404）、OCR服务不可用（503）和输入格式错误（400）。需要建立合理的异常处理机制。
