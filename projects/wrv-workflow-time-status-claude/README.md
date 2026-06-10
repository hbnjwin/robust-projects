# wrv-workflow-time-status

## Question ID: l1-069

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

AI报告审查的工作流历史记录展示有三个问题：1) 返回的时间戳是 UTC 格式（如 2024-03-15T08:30:00Z），页面直接显示了原始字符串没有转成本地时间；2) 工作流状态标签的颜色映射写反了，completed 显示黄色警告而不是绿色成功，warning 反而显示绿色；3) 正在执行中的任务（状态 started）的查看详情按钮应该禁用但现在可以点击，点了之后弹窗里显示不完整的数据。
