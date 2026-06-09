# wrr-darkmode-popup-leak

## Question ID: l1-036

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

暗色模式切换后，Element Plus 的一些弹窗组件（MessageBox、Notification、Popover）颜色还是亮色主题的白底黑字，跟暗色背景很突兀。看了下 app store 的 setCssVar 逻辑只处理了 app 容器内的变量，但弹窗是挂在 body 下面的 teleport 元素。
