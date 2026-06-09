# wrr-chat-api-dedup

## Question ID: l1-060

## Task Type: refactor-maintenance

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

AI 对话的 API 定义，api/ai/chat/message/ 和 api/student/chat/message/ 两个目录下的代码几乎一样，ChatMessageVO 接口定义了两份，ChatMessageApi 对象也重复了。学生版只多了 exportChatMessage 和 submitStatus 两个方法。帮我重构合并，提取公共部分到 shared 模块。
