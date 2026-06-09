# wrr-ime-enter-conflict

## Question ID: l1-035

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

AI 对话输入框，用中文输入法打字然后按回车确认选词，消息会被直接发出去而不是先完成输入法的选词。搜狗输入法和微软拼音都有这个问题。代码里有 compositionstart/compositionend 事件处理但好像和 keydown Enter 的时序对不上。
