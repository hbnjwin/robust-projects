# wrv-task-detail-xss

## Question ID: l1-063

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

AI报告审查的任务详情弹窗有两个严重问题。第一，检查结果的审查意见用 v-html 直接渲染，如果上游文档内容里包含 <script> 标签或 onclick 属性，会被原样执行，存在 XSS 风险。第二，结果文本里有些字段是 null，页面显示了 "null" 字符串而不是空白。第三，检查结果的通过/警告/失败统计数字跟详情列表实际展示的数量对不上，看着是统计接口和列表接口的数据口径不一致。帮我都修了。
