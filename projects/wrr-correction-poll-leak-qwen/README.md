# wrr-correction-poll-leak

## Question ID: l1-038

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

AI 批改页面，老师启动批改后进度条开始定时轮询。但如果中途切换到其他页面（没有关闭标签页），再切回来发现进度数字一直在跳，因为又启动了一个新的定时器，旧的那个在页面不可见时也没停。帮我修下这个定时器泄漏。
