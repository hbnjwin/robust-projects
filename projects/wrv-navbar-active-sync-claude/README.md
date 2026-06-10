# wrv-navbar-active-sync

## Question ID: l1-070

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

顶部导航菜单的选中态同步问题。进入 AI 报告审查页面后菜单高亮正确，但在页面内操作（打开任务详情弹窗、执行审查等）后关闭弹窗，菜单的 active 状态偶尔丢失变成没有任何菜单高亮。原因是弹窗的 Dialog 组件触发了路由的 hash 变化。而且浏览器前进后退按钮操作时菜单高亮不跟着路由变化更新，nav-bar 组件只在 mounted 时读了一次 route.path。
