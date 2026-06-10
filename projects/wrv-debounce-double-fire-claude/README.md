# wrv-debounce-double-fire

## Question ID: l1-091

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

搜索框用了 debounce 防抖（common-function.js），但输入停止后搜索请求发了两次。检查发现 immediate=true 模式下先立即执行了一次，setTimeout 结束后又执行了一次。而且如果把 immediate 设成 false 想延迟执行，回调函数又完全不触发了。需要修复 debounce 函数的 immediate 判断逻辑，确保 immediate=true 时只在首次触发，immediate=false 时在延迟结束后触发。