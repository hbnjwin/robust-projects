# wrr-workflow-proc-dup

## Question ID: l1-138

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

系统中有三个工作流处理器类——WorkflowProcessor（505行）、EnhancedWorkflowProcessor（1241行）和LLMWorkflowProcessor（689行），它们之间存在大面积的代码复制。parseSelectedItems()、getExtractionRules()、getCheckItems() 这三个数据查询方法在三个类中近乎逐字相同；handleWorkflowEvent() 和 processStreamResponse() 的SSE事件解析逻辑被复制了三份；buildExtractionRequestBody() 和 buildCheckRequestBody() 的请求体构建代码也高度重复。当工作流的事件格式需要调整时，开发者必须找到三个类中对应的位置分别修改，已经出现过漏改一处导致某个处理器行为不一致的情况。需要消除三个处理器之间的重复代码。
