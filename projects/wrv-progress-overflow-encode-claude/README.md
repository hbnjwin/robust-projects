# wrv-progress-overflow-encode

## Question ID: l1-067

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

任务进度组件（task-progress）有三个问题：1) 当审查任务包含大量检查项（50+个）时，进度百分比计算出现浮点精度问题显示 101%，TDesign 的 Progress 组件直接报 props 验证错误；2) 进度信息文本有编码乱码，组件源码里确实有 GBK 编码问题的中文注释；3) 任务完成瞬间进度会闪一下 0% 然后变成 100%，因为 WebSocket 推送的完成消息和最后一次进度更新的时序不确定。
