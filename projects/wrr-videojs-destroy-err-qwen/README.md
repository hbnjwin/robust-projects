# wrr-videojs-destroy-err

## Question ID: l1-042

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

学生端课程视频页面，播放完一个章节的视频后切到下一个章节，控制台报了一堆 video.js 的 Cannot read properties of null 错误，有时候还直接白屏。看起来是路由切换时 video.js 实例的 dispose 和 Vue 组件的 onUnmounted 执行顺序有问题。
