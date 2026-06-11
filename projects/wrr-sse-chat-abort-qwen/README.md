# wrr-sse-chat-abort

## Question ID: l1-031

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

AI 对话页面，用户连续快速发消息然后点停止，之后整个对话就卡住了，新消息发不出去。看了下代码是 fetchEventSource 的 AbortController 状态没清理干净，停止后 isStreaming 标志位还是 true。帮我排查修一下。
