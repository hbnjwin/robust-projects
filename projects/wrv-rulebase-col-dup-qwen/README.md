# wrv-rulebase-col-dup

## Question ID: l1-096

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

系统管理的规则库页面（system/rulebase/index.vue）表格显示异常：「版本号」和「备注」两列显示了完全相同的数据。检查 tableColumns 定义发现这两列的 colKey 都写成了 "creator"，TDesign 表格根据 colKey 映射数据字段，两列都渲染了 row.creator 的值。另外表格的列名和 colKey 的映射整体都有偏差——比如「创建时间」对应的 colKey 是 "deadline"，「创建人」对应的 colKey 是 "status"。需要修正 colKey 映射，让每列对应正确的数据字段，同时消除重复 key。