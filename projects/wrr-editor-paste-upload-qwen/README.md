# wrr-editor-paste-upload

## Question ID: l1-059

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

新闻编辑页的富文本编辑器（WangEditor），从浏览器或者微信复制图片粘贴进去后，编辑时能看到图片，但保存后重新打开图片全丢了。查了下是粘贴进来的图片是 base64 格式，没有自动上传到文件服务器转成 URL。
