# wrr-controller-fat

## Question ID: l1-148

## Task Type: refactor-maintenance

## App Domain: data_engineering

## Language: java

## Model: qwen

## Query

TasksController 的 executeCheckTask 方法（89-185行，约100行代码）直接在 Controller 层执行了大量业务逻辑：通过 QueryDSL 查询数据库获取任务和文档实体、读取文档的 Markdown 内容、构建工作流事件处理器的回调函数、调用工作流处理器并处理流式响应结果、将结果数据组装成 Map 返回。此外 convertWorkflowResultToJson 私有方法（517-567行）在 Controller 中执行了数据格式转换。AiController 中也有类似问题，同一段 Hutool JSONObject 转 Map 的代码（包含 JSONNull 类型判断）在四个端点方法中被完全复制了四次（63-74、108-115、189-199、244-254行）。这些逻辑无法被定时任务、批量处理API或WebSocket入口复用，也难以编写单元测试。需要将业务逻辑从 Controller 层提取到 Service 层。
