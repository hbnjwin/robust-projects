# wrr-order-amount-precision

## Question ID: l1-046

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: claude

## Query

教育订单模块，有用户反馈支付 99.9 元的课程包，结算页显示 99.89999999999999 元。查了一下 EduOrderDO 用的 Double 存金额，帮我改成 BigDecimal 并修复 Controller 和 Service 层所有涉及金额计算的地方。
