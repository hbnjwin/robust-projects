# wrv-custom-column-drift

## Question ID: l1-066

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

表格自定义列配置（CustomHeader 组件），用 SortableJS 拖拽调整列顺序后保存到 localStorage。但有个渐进式退化问题：后端新增了一个字段后，localStorage 的配置里没有这个字段，新字段就永远不会出现在表格里。而且后端删掉了的老字段缓存里还存在，表格渲染时报 key 重复的 warning。需要做缓存和后端列定义的 diff 同步，新增的补到末尾，已删除的清理掉。
