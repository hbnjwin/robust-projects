# wrr-order-mapper-inject

## Question ID: l1-048

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

订单模块的 EduOrderController 直接 @Resource 注入了 EduOrderMapper 和 PaymentRecordMapper 做查询，完全跳过了 Service 层。导致事务管理没生效，数据权限拦截器也被绕过了。帮我重构到正确的三层架构，把查询逻辑下沉到 Service。
