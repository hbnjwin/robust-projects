# wrr-wechat-callback-idem

## Question ID: l1-051

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

微信支付回调接口偶尔出现验签失败，看日志是 HttpServletRequest 的 body 被读了两次。而且回调处理不是幂等的，同一笔支付通知处理了两次导致订单金额翻倍。帮我修复 body 读取和幂等性问题。
