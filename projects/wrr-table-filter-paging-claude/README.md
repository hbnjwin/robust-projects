# wrr-table-filter-paging

## Question ID: l1-001

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

我们这个 React + TypeScript 的后台管理系统，用户反馈表格组件在筛选条件变化后，分页会跳回第一页，但表格数据没刷新，还是显示上一次筛选的结果。只有手动点一下分页才会更新。你帮我排查下这个 bug，改掉它。项目用的 antd 的 Table 组件，数据走的 useRequest 请求。
