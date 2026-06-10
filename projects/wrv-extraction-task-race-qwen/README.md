# wrv-extraction-task-race

## Question ID: l1-075

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

数据提取任务并发执行问题。ExtractionTasksService 在创建提取任务时没有幂等检查，两个管理员几乎同时对同一批文档发起提取，生成了两组完全重复的 ExtractionTasksItems 记录，导致提取结果也翻倍了。而且任务状态从 queued 变为 running 的更新没有用乐观锁，偶尔出现数据库里任务还是 queued 但线程已经在跑提取的情况。帮我加上基于文档ID的幂等检查和状态更新的乐观锁。
