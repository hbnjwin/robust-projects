# wrr-java-rbac-explain

## Question ID: l1-027

## Task Type: bug-fix

## App Domain: backend_service

## Language: java

## Model: claude

## Query

这个 Java 项目的权限模块有 bug，有些接口明明配置了权限注解但没生效，角色继承关系也乱了，子角色居然比父角色权限还大。帮我查下问题修一下，顺便把权限缓存的一致性也处理下。
