# wrv-upload-cancel-leak

## Question ID: l1-071

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

文档上传过程中点取消，axios 请求没有被 abort，文件继续在后台传输浪费带宽。取消后如果重新打开上传弹窗，上次的上传进度状态还残留着，进度条显示一个错误的百分比。而且上传弹窗的 beforeClose 回调里没有清理 FormData 对象和文件引用。如果连续快速打开关闭弹窗几次，会看到内存持续增长。
