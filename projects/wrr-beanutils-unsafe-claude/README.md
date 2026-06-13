# wrr-beanutils-unsafe

## Question ID: l1-147

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: claude

## Query

DocumentsServiceImpl 和 TasksServiceImpl 等服务类中有30处以上使用 Spring 的 BeanUtils.copyProperties() 在 Entity 和 Info/DTO 对象之间进行属性拷贝。这些拷贝是在运行时通过反射完成的，当某个 Entity 字段被重命名后，copyProperties 不会报错而是静默跳过该字段，导致 API 响应中对应字段变成 null，排查成本极高。DocumentsServiceImpl 中至少有7处（165、209、236、269、281、313、335行），TasksServiceImpl 中有8处以上（156、209、276、304、349、384、395、411行）。此外 TasksServiceImpl.createOrUpdate 在修改分支中特意排除了 title 和 status 字段的拷贝（304行），这种意图在 BeanUtils 的方式下只能通过 ignore 参数传字符串数组来表达，容易被忽略。需要重构为编译时可验证的类型安全映射方式。
