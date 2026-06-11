# wrr-chat-scroll-conflict

## Question ID: l1-043

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

AI 对话消息列表，收到流式回复时应该自动滚到底部，但如果用户之前手动往上翻看了历史消息，新消息一来又被强制拉到底部。用户正在看历史记录的时候体验很差。需要实现用户主动滚动时暂停自动滚动的逻辑。
