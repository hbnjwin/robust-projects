# wrv-task-cascade-orphan

## Question ID: l1-079

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

删除审查任务时，Tasks 表的记录删了但关联的 TasksCheckItems 和 CheckResult 表数据没有级联删除，变成了孤儿数据。积累几个月后这两个表的数据量是 Tasks 表的几十倍，严重影响查询性能。更严重的是，如果删除的任务状态还是 started（正在执行），Quartz 调度的线程会继续往已删除的 task_id 写 CheckResult，最后 NPE 导致线程池里的线程挂掉。
