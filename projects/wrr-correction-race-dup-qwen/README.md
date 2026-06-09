# wrr-correction-race-dup

## Question ID: l1-049

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

AI 批改功能，两个老师几乎同时对同一个班级发起批改，出现了重复的 correction 记录和重复的 PaperCorrectionTask。任务状态还卡在 running 不变。CorrectionService 的创建逻辑没有做并发控制，帮我加上幂等检查和分布式锁。
