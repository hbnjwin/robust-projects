# wrv-batch-check-queue

## Question ID: l1-082

## Task Type: feature

## App Domain: backend_service

## Language: java

## Model: claude

## Query

审查任务目前只能逐个文档创建，运营人员经常要一次审查几十份风电报告。帮我做一个批量创建审查任务的功能：支持按项目或文档类型批量选择文档，选择检查模板后一键创建多个审查任务。加入优先级队列机制（紧急/普通/低优先级），Quartz 调度时优先执行紧急任务。提供批量任务的整体进度查询接口，返回总任务数、已完成数、失败数。
