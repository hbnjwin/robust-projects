# wrr-route-role-dup

## Question ID: l1-034

## Task Type: bug-fix

## App Domain: web_frontend

## Language: ts

## Model: claude

## Query

用户切换角色（比如从管理员切到教师）后，菜单变了但点某些菜单项会报路由重复添加的警告，偶尔还直接白屏。刷新页面就好了。看着是 permission store 的 generateRoutes 在角色切换时没有先清理旧路由就添加新路由。
