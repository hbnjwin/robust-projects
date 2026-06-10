# wrv-check-regex-redos

## Question ID: l1-077

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: claude

## Query

CheckItems 表里有些检查项的 regex 字段包含有回溯风险的正则表达式，当审查文档内容很长时正则匹配 CPU 占用飙升，单个检查项卡住几分钟，阻塞了整个审查任务队列。需要对 CheckItems 的 regex 字段加入 ReDoS 风险检测（保存时校验），并给运行时正则匹配加上超时中断机制。
