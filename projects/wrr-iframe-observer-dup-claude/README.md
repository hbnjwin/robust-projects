# wrr-iframe-observer-dup

## Question ID: l1-045

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

JB 第三方集成页面用 iframe 嵌入了外部系统，但反复在标签页之间切换后，iframe 的高度自适应就不正常了，底部被截断。查了下代码发现 MutationObserver 在 keep-alive 激活时重复创建但旧的没有 disconnect，同时 instanceId 的 Symbol 检查逻辑也有竞态。
