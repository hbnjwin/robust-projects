# wrr-cicd-cache-mirror

## Question ID: l1-029

## Task Type: bug-fix

## App Domain: devops_infrastructure

## Language: shell

## Model: claude

## Query

CI/CD 构建老失败，依赖下载超时是一方面，还有个问题是缓存命中率为零——每次都在重新编译。看了一下是缓存key的生成逻辑有问题，而且多分支并行构建的时候缓存还会互相覆盖。帮我修一下构建脚本，把缓存、镜像源、并行构建冲突都处理好。
