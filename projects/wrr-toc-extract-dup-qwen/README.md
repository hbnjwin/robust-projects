# wrr-toc-extract-dup

## Question ID: l1-141

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

DocumentOcrProcessorService 和 DocumentsServiceImpl 之间存在两段完全逐字复制的代码。第一段是 processTocData() 方法（约70行），负责解析文档目录结构、构建 DocumentsToc 实体列表并批量保存，两个类中的实现从方法签名到内部逻辑完全相同。第二段是 createExtractionTasks() 方法（约85行），负责根据抽取规则创建 ExtractionTasks 记录，包括查询规则配置、构建任务实体、设置关联字段、保存数据库，两个类中也是逐字复制。这两段代码总计约155行在两个服务类之间完全重复，修改目录解析逻辑时容易只改一处而遗漏另一处。需要消除这种跨服务类的代码重复。
