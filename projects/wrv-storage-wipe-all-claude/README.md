# wrv-storage-wipe-all

## Question ID: l1-121
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

每次退出登录后重新登录，发现之前自定义的表格列配置（列的显示/隐藏、排序）全部丢失，恢复成默认状态。排查发现 src/store/modules/table.js 的useTableStore使用了pinia的persist:true持久化到localStorage。但 src/layout/nav-bar/index.vue 的signOut函数（第79-84行）中调用了oauth2.remove()和localStorage.clear()。oauth2.remove()内部（src/utils/oauth2.js第42-45行）已经调用了Cookies.remove(KEY)清除认证cookie，但额外还调了一次localStorage.clear()清除所有本地存储。signOut函数第84行又重复调用了localStorage.clear()。两次localStorage.clear()把所有pinia持久化的store数据全部清空，包括useTableStore保存的表格列自定义配置。正确做法是oauth2.remove()只清除自己的cookie，不应该清localStorage；signOut中也应该只清除特定的auth相关key，而非全部清空。
