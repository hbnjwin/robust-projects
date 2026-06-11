# wrv-debounce-ctx-lost

## Question ID: l1-129
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

使用项目工具库中的debounce函数包装组件方法后，方法内部的this指向丢失，无法访问组件实例属性；同时传入的参数（如事件对象event、搜索关键词等）在被调用时变成undefined。排查 src/utils/common-function.js 第62-76行的debounce实现发现，返回的wrapper函数内部直接调用func()，没有使用func.apply(this, arguments)或func.call(this, ...args)转发执行上下文和参数。在JavaScript中，当wrapper函数作为对象方法被调用时，this指向该对象，但内部直接调用func()时this变成undefined（严格模式）或window（非严格模式）。同样，调用wrapper('keyword')传入的参数'keyword'也因为func()调用时没有传递arguments而丢失。这导致任何依赖this上下文（如访问组件data/methods）或需要接收参数（如搜索输入框的debounce）的使用场景都会失败。需要将func()改为func.apply(this, arguments)来正确转发上下文和参数。
