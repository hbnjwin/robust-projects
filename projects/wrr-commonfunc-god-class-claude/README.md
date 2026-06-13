# wrr-commonfunc-god-class

## Question ID: l1-137

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: claude

## Query

项目的 support 包中有一个 CommonFunc 类，大约1500行代码，承担了十几种完全不相关的职责：JPA Specification 动态条件构建、EntityManager 原生SQL查询执行、树结构递归操作、日期时间格式化、反射字段访问、MVEL表达式求值、Azure OpenAI 流式对话、Linkyoyo Agent AI 调用、DeepSeek AI 调用、OkHttp 通用AI请求、文件读写操作、列表内存分页、反射排序等。任何一个职责的修改都要打开这个巨大的文件，而且不同职责之间存在隐含的耦合（比如AI调用方法引用了内部的SSL配置方法）。需要对这个类进行拆分重构，将不同职责提取到各自独立的服务类中。
