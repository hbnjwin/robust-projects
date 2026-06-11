# wrv-i18n-loader-array

## Question ID: l1-106

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

项目集成了 vue-i18n 但所有页面的翻译键都显示原始 key 而非翻译文本。排查 lang/index.js 的消息加载逻辑发现，import.meta.glob 获取的模块经过 Object.values(modules).flat(1) 处理后变成了数组 [{}]，然后赋值给 messages[lang]。但 vue-i18n 要求 messages 格式为 { zh_Hans: { key: 'text' } }（对象），不是数组。另外循环中每次处理新文件都用 messages[lang] = values 直接覆盖，同一语言下多个翻译文件的内容不会合并，只有最后一个文件生效。需要将 flat 改为 reduce 合并，确保输出为嵌套对象结构。