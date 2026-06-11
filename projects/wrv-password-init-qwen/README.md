# wrv-password-init

## Question ID: l1-111
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

密码强度组件在页面首次加载时始终显示0颗星，即使父组件传入了非零的strength属性值。排查发现 src/components/password-strength/index.vue 中，data()将内部value初始化为0，watch监听strength属性来同步value值，但watch没有设置immediate:true。Vue的watch默认只在属性变化时触发，不会在组件挂载时对初始值触发回调。因此当父组件以 <password-strength :strength="3"/> 方式使用时，内部value保持为0，t-rate组件渲染0颗星，直到strength属性发生第二次变化才会同步。同时注意到computed属性text直接读取props.strength而非内部value，导致文字描述正确但星级显示为0，视觉上不一致。需要给watch添加immediate:true或者在data()中用props.strength初始化value。
