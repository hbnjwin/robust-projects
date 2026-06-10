# wrv-pagination-prop-mutate

## Question ID: l1-094

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

表格分页组件（table-pagination/index.vue）的翻页功能在控制台一直报 Vue 的 prop mutation 警告。查看代码发现模板里用了 v-model="props.pagination.page" 直接双向绑定到了 props 的嵌套属性上，违反了 Vue 的单向数据流。翻页时虽然能跳页，但父组件无法感知页码变化来重新请求数据，列表数据不会刷新。需要改成通过 emit 事件通知父组件更新，或使用 computed + emit 实现双向绑定。