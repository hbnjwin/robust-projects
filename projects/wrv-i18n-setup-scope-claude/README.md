# wrv-i18n-setup-scope

## Question ID: l1-117
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

项目启动后，任何尝试切换语言或读取当前语言的操作都会报错：Must be called at the top of a setup function。排查 src/lang/index.js 发现第34-43行定义了两个导出：setLocaleOnClient函数和lang计算属性，它们内部都调用了useI18n()。但useI18n()是Vue I18n的组合式API，内部使用inject()获取i18n实例，必须在Vue组件的setup()函数上下文中调用。这两个导出定义在普通JS模块的顶层作用域，不在任何组件的setup()中。当lang计算属性在模块首次被import时就会求值其getter函数，此时没有活跃的组件实例，useI18n()必然抛出错误。setLocaleOnClient同理，除非恰好从某个组件的setup中调用它（但通常是从路由守卫或工具函数中调用）。需要改为使用全局i18n实例（如import的i18n对象的.global属性）来替代useI18n()。
