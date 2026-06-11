# wrv-align-invalid

## Question ID: l1-113
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

应用顶部导航栏的三个子元素（logo、菜单标签、用户信息）在垂直方向上没有正确对齐，而是被拉伸到了导航栏的全部高度。排查 src/layout/nav-bar/index.vue 的样式发现，.app-header设置了display:flex，但align-items属性的值写成了space-between。space-between是justify-content的有效值，用于在主轴方向上分配间距，但它不是align-items的合法值。align-items的合法值包括flex-start、flex-end、center、baseline、stretch等。浏览器遇到无效的CSS属性值会静默忽略，回退到默认值stretch，导致所有子元素在交叉轴（垂直方向）上被拉伸填满。需要将align-items的值修正为center以实现垂直居中对齐。
