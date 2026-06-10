# wrv-filter-state-leak

## Question ID: l1-064

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

专家库页面选了"可研报告"类型筛选后，切到AI报告审查页面再切回来，筛选下拉框变成了默认值但表格数据还是筛选后的结果。是路由切换时组件的 filterParams 对象和实际发出的请求参数不同步。而且排序字段在页面切换后也没有重置，偶尔出现按不存在的字段排序导致后端返回 500。分页的 current 页码也有类似问题，切回来后显示第1页但请求带的还是之前的页码。
