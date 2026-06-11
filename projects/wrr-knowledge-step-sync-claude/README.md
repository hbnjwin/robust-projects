# wrr-knowledge-step-sync

## Question ID: l1-037

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

知识库文档上传分三步走（上传文件、自动分片、向量处理），但经常第二步 API 返回成功了界面还卡在第一步的 loading 状态。刷新后发现数据已经处理好了。看着是步骤组件的状态更新时机和后端回调不同步。
