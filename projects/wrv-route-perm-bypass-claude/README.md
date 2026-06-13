# wrv-route-perm-bypass

## Question ID: l1-131

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

系统有角色权限控制的设计（路由配置了 auth 字段区分不同页面的访问权限，也有一个 403 无权限页面），但实际测试发现两个问题：1）任何已登录用户在浏览器地址栏直接输入 /system/management 或 /system/rulebase 都能正常访问，不会被拦截到 403 页面；2）左侧导航菜单对所有用户显示完全相同的菜单项，包括"系统管理"等应该只对管理员可见的入口。需要排查路由守卫和导航菜单的权限控制逻辑。
