# wrv-token-expire-loop

## Question ID: l1-093

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

登录成功后页面一直在登录页和首页之间死循环跳转。排查发现登录流程中调用 oauth2.setOauth() 时只传了 access_token，没有传 expires_in 字段。oauth2.js 的 setOauth 方法用 dayjs().add(oauth.expires_in, "seconds") 计算过期时间，但 expires_in 是 undefined，dayjs.add(undefined) 返回当前时间，导致 token 刚存进去就被判定过期。路由守卫检查 isTokenExpired() 为 true 后又跳回登录页，形成死循环。需要在登录时正确传入 expires_in，并在 setOauth 中对 expires_in 缺失做兜底处理。