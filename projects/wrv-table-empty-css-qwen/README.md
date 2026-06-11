# wrv-table-empty-css

## Question ID: l1-112
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

表格空状态的样式在整个应用中表现异常——某些页面的表格空状态区域高度突然变大。排查发现 src/components/table-empty/index.vue 的style标签没有scoped属性，其中定义了 .el-table__empty-block { min-height: 250px !important; } 这条全局CSS规则。问题有两个：第一，这个组件的CSS泄漏到了所有页面，影响了所有包含该类名的元素；第二，.el-table__empty-block 是Element Plus框架的类名，但项目的表格组件主要使用TDesign的t-table，TDesign的空状态类名是.t-table__empty而非.el-table__empty-block。这条规则要么没有命中目标（TDesign表格），要么错误地影响了Element Plus表格的样式。需要将style改为scoped，并将选择器修正为TDesign对应的类名。
