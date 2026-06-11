# wrv-i18n-glob-self

## Question ID: l1-128
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

国际化翻译配置在添加翻译文件后仍然无法正常工作，且控制台出现递归引用的警告。排查 src/lang/index.js 第4行的 import.meta.glob('./**/*.js', { eager: true }) 发现这个glob模式会匹配当前目录下所有.js文件，包括index.js自身。这意味着langModules对象中包含了一个key为'./index.js'的条目，其值是index.js模块导出的所有内容（包括i18n实例、setLocaleOnClient函数、lang计算属性等）。在第7行的循环中，path.split('/')[1]对'./index.js'的结果是'index.js'，于是messages对象中产生了一个key为'index.js'的语言条目，其内容是index.js的导出而非翻译数据。这污染了i18n的messages结构，如果某个语言文件夹名恰好是'index.js'还会发生覆盖。需要修改glob模式排除index.js自身，如使用'./*/*.js'只匹配子目录中的文件，或添加 { eager: true, import: 'default' } 只取default导出。
