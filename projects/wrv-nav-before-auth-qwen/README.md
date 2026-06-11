# wrv-nav-before-auth

## Question ID: l1-120
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

登录偶尔会出现循环跳转——提交正确的账号密码后页面短暂闪烁然后又回到登录页。排查 src/pages/login/index.vue 第76-79行发现，登录成功后的代码执行顺序有问题：先调用router.push({ name: 'Expert' })发起路由跳转，然后才执行userInfo.value = user和oauth2.setOauth({ access_token: accessToken })存储认证信息。router.push()是异步的，它触发的路由导航会经过beforeEach守卫。守卫中检查oauth2.getOauth()来判断用户是否已登录（router/index.js第56行），但此时setOauth还没执行，cookie中没有token，守卫判定未登录并重定向回Login页面。虽然JavaScript事件循环中microtask的执行时序可能让这个竞态不是每次都触发，但在某些浏览器或较慢设备上会稳定复现。正确的做法是先存储认证信息，再执行路由跳转。
