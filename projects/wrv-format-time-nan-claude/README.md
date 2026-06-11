# wrv-format-time-nan

## Question ID: l1-123
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

任务进度组件的消息日志区域中，所有日志条目的时间戳都显示为"Invalid Date"而不是实际时间。排查 src/components/task-progress/index.vue 发现存在双重格式化问题。addLog函数（第229-235行）将日志的time字段存储为 new Date().toLocaleTimeString() 的返回值，这是一个已经格式化的字符串（如"下午3:45:30"或"15:45:30"）。模板中调用formatTime(log.time)展示时间，而formatTime函数（第219-227行）尝试用new Date(timeStr)将这个字符串解析回Date对象。但JavaScript的Date构造函数无法可靠解析locale格式的时间字符串（尤其是中文环境下的"下午3:45:30"），返回Invalid Date对象。Invalid Date调用toLocaleTimeString()得到字符串"Invalid Date"。try-catch不能捕获这个问题，因为new Date()不会抛出异常，它静默返回Invalid Date。需要将addLog中的time改为存储Date对象（new Date()），或者修改formatTime直接返回传入的字符串。
