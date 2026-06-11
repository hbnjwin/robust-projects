# wrr-homework-auth-hole

## Question ID: l1-047

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: qwen

## Query

安全扫描报了作业模块的接口漏洞，HomeworkController 里好几个接口的 @PreAuthorize 注解被注释掉了换成了 @PermitAll，意味着未登录用户也能调用发布作业、批改作业这些接口。帮我把权限注解补回去，并且确保每个接口都有正确的权限码。
