# wrr-chunk-md5-block

## Question ID: l1-044

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

上传大文件课件（超过100MB的视频）时，页面直接卡住好几秒完全不能操作。看了下是 spark-md5 在计算文件哈希的时候同步读取整个文件阻塞了主线程。需要改成 Web Worker 或者分片异步计算。
