# wrv-table-resize-shadow

## Question ID: l1-072

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

专家库和 AI 审查页面的 TDesign 表格，在浏览器窗口缩放或者 F11 全屏切换后，表格列宽不会自动重新计算，最后一列被挤出视口出现横向滚动条。而且固定列（如操作列）的阴影效果在表格数据刷新后消失，需要手动横向滚动一下才会重新出现。resize 事件的 debounce 时间太长（500ms），窗口拖拽缩放时表格布局跳动明显。
