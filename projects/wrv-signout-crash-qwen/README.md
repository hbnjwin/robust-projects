# wrv-signout-crash

## Question ID: l1-104

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

点击右上角退出登录后，页面没有正常跳转到登录页，而是控制台报 TypeError: Cannot read properties of null (reading 'operatorName')。排查 nav-bar/index.vue 的 signOut 方法发现，router.push({ name: 'Login' }) 是异步操作，但紧接着同步执行了 userInfo.value = null 和 localStorage.clear()。由于页面有 0.3 秒的路由过渡动画，在动画期间 nav-bar 模板中的 {{ userInfo.operatorName }} 尝试读取已被设为 null 的 userInfo，导致崩溃。另外 localStorage.clear() 会清除所有应用数据而不仅是用户信息，影响其他功能的本地存储。需要先 await 路由跳转完成，或者将 userInfo 设为空对象而非 null。