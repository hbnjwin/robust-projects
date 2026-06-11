# wrv-port-regex-flip

## Question ID: l1-107

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

系统设置页面的端口号输入框验证时有时通过时有时不通过，同一个合法端口号（如 8080）连续验证结果交替变化。排查 utils/validate.js 的 port 方法发现正则表达式 /^(\d)+$/g 带了 g 全局标志。JavaScript 中对带 g 标志的 RegExp 对象调用 test()，会在内部维护 lastIndex 状态：第一次调用匹配成功后 lastIndex 移到末尾，第二次调用从 lastIndex 开始匹配失败并重置为 0，第三次又成功，如此交替。在表单校验场景中（每次 blur 或输入都触发），同一个端口号会随机显示"格式错误"。需要去掉正则的 g 标志。