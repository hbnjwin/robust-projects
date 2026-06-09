# wrr-tags-cache-stale

## Question ID: l1-039

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

后台的标签页导航，打开 A 页面设置了表格筛选条件，然后切到 B 页面再切回来，A 页面的筛选表单被重置了但表格数据还是筛选后的结果。keep-alive 缓存的组件状态和 URL 参数不一致，导致用户看到的数据是错的。
