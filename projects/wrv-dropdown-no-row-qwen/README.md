# wrv-dropdown-no-row

## Question ID: l1-105

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

专家库页面表格的操作列有一个下拉菜单，包含「删除」选项。点击删除后没有任何反应——不弹确认框也不发请求。排查发现 t-dropdown 的 @click 事件绑定了 clickHandler(data)，但 TDesign 的 dropdown click 事件只传递选项的 value（本例中是数字 1），不传递表格行数据。虽然 dropdown 渲染在 template #link="{ row }" 插槽里可以访问 row，但 clickHandler 的参数签名没有接收 row，handler 内部也只有一行 console.log(data)，没有任何实际的删除逻辑。需要通过闭包将 row 传入 handler，并实现确认弹窗和删除 API 调用。