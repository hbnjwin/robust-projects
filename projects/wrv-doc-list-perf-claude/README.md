# wrv-doc-list-perf

## Question ID: l1-068

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

专家库文档列表页面，每次切换筛选条件或翻页都会把整个表格数据深拷贝存到 tableStoreColumns（Pinia + localStorage）。长时间使用后 localStorage 存储量越来越大。用 DevTools 看内存快照发现 reactive 嵌套的代理对象没有被回收。打开页面加载100条文档数据后明显变卡，表格滚动掉帧。帮我优化下这个列配置的存储逻辑，不要把表格数据存进去，只存列的显隐和排序信息。
