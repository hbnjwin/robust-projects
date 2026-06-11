# wrv-sortable-wrong-el

## Question ID: l1-122
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

自定义表头组件的列拖拽排序功能不生效——打开列配置抽屉后，尝试拖拽调整列顺序时，拖拽的不是配置列表而是背后的数据表格行，且会导致数据表格的行顺序混乱。排查 src/components/custom-header/index.vue 的registerSort函数（第64-66行）发现，document.querySelector('.el-table__body-wrapper tbody') 使用全局选择器获取表格DOM元素来初始化Sortable拖拽。但querySelector返回的是文档中第一个匹配的元素。当列配置抽屉打开时，页面上同时存在两个表格：一个是底层的数据表格（先渲染），一个是抽屉内的列配置表格。querySelector选中了先渲染的数据表格的tbody，将Sortable绑定到了错误的元素上。需要改为使用ref引用或限定选择器的作用域（如在抽屉容器内查找），确保选中的是抽屉内的列配置表格。
