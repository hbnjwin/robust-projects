# wrv-home-path-dup

## Question ID: l1-130
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: claude

## Query

在尝试同时启用主页模块和专家库模块后，发现两个模块的页面出现路由混乱——有时主页的菜单打开了专家库的页面，有时专家库的子路由渲染到了主页的layout中。排查路由配置发现 src/router/modules/home.js 第6行和 src/router/modules/expert-database.js 第5行都定义了path: '/'作为根路由。在Vue Router中，同一层级不应有两个相同path的路由，否则只有第一个匹配的路由会生效，或者两个路由的children会产生不可预期的覆盖行为。当routerModules数组中同时包含这两个模块时，router.addRoute或routes数组中存在两条path:'/'的记录，Vue Router的路径匹配是按注册顺序优先的，后注册的路由可能被忽略或覆盖。此外两个模块各自定义了不同的redirect目标（Home重定向到CreateReview，Expert重定向到ExpertDatabase），进一步加剧了冲突。需要给其中一个模块修改path避免冲突，如将Home的path改为'/home'。
