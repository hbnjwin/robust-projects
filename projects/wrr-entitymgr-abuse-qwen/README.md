# wrr-entitymgr-abuse

## Question ID: l1-149

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

ExtractionTasksServiceImpl、CheckResultServiceImpl、ExtractionResultServiceImpl、TasksServiceImpl、DocumentsServiceImpl 等7个服务实现类在执行 findById 查询前都调用了 entityManager.clear()，整体清空 JPA 一级缓存。ExtractionTasksServiceImpl 中有两处（105行和160行），TasksServiceImpl 在301行，DocumentsServiceImpl 有三处（233、266、579行）。这个做法是为了规避脏读问题，但它同时丢弃了该 EntityManager 中所有已加载实体的状态，是一个性能反模式。同时这些类的 createOrUpdate 方法都缺少 @Transactional 注解，多步数据库操作（删除旧子记录、保存新主记录、保存新子记录）没有事务保护，中途失败会导致数据不一致。此外 ExtractionTasksServiceImpl 的子记录保存（77-82、96-101、126-131、145-150行）和 TasksServiceImpl 的子记录保存都在 for 循环中逐条调用 repository.save()，而非使用 saveAll() 批量保存。需要修复这些 JPA 使用上的问题。
