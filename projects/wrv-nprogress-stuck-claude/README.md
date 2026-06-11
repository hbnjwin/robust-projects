# wrv-nprogress-stuck

## Question ID: l1-101

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

路由跳转到403或404页面时，顶部蓝色进度条一直停留不消失。排查发现 router/index.js 的 beforeEach 守卫中，对 baseRouterNames 包含的路由（403、404、login等）走了 early return next()，但之前已经调用了 nprogress.start()，这个分支没有调用 nprogress.done()。其他所有分支（已登录、未登录、无权限）都正确调用了 nprogress.done()，唯独这个分支遗漏了。而且整个路由配置中也没有注册 router.afterEach 钩子来兜底清理。需要在 base 路由分支添加 nprogress.done()，并建议增加 afterEach 兜底。