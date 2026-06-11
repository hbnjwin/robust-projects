# wrr-permi-directive-vfor

## Question ID: l1-041

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: qwen

## Query

有个管理页面里用了 v-hasPermi 自定义指令控制操作按钮的显示，在静态写死的按钮上没问题，但在 v-for 循环里动态渲染的按钮，权限判断全部失效了，不该显示的按钮也显示出来了。帮我查下指令在列表渲染场景的问题。
