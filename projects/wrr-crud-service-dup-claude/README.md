# wrr-crud-service-dup

## Question ID: l1-140

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: claude

## Query

CheckResultServiceImpl、DocumentsExtractionServiceImpl、ExtractionResultServiceImpl、ExtractionTasksServiceImpl、TasksServiceImpl、DocumentsServiceImpl 这六个以上的服务实现类，它们的 createOrUpdate 方法遵循完全相同的编码模式：先判断 info.getId() 是否为空来区分新增和修改，然后用 BeanUtils.copyProperties 在 Entity 和 Info 之间拷贝属性，调用 repository.save()，再对子表记录执行先全删后逐条新增的操作。TasksServiceImpl 的 createOrUpdate 方法甚至在新增分支（约90行）和修改分支（约75行）之间复制了完全相同的子表保存逻辑（CheckResult 和 TasksCheckItems 的删除-重建代码各出现两次）。每次新增一个业务实体都要重新复制一遍这套样板代码。需要重构提取通用的增删改查模式。
