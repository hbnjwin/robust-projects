# wrv-i18n-key-display

## Question ID: l1-073

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

项目引入了 vue-i18n 但 lang 目录下的 locale 文件里中英文都是空对象，页面上用 $t() 的地方都显示 key 字符串如 "system.login.title" 而不是实际文案。有些组件用了 $t() 有些直接写的中文硬编码，极不统一。偶尔还会在控制台看到 vue-i18n 的 missing translation 警告刷屏。要么把中文 locale 补全要么去掉 vue-i18n 用硬编码统一，现在这个半成品状态不能上线。
