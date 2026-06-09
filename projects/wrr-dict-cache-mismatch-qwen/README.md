# wrr-dict-cache-mismatch

## Question ID: l1-033

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

系统字典加载后，有些下拉框能正常显示字典值，有些页面却显示空白。看了下代码 dict store 里 dictDataMap 声明的是 Map 类型但好多地方用中括号语法访问，而且 sessionStorage 的缓存过期时间 60 秒太短了，频繁重新加载。帮我排查这个类型不匹配的问题修一下。
