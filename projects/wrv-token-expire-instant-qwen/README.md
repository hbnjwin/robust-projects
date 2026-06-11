# wrv-token-expire-instant

## Question ID: l1-114
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

登录成功后，用户很快就会遇到token过期被踢回登录页的问题，正常的token有效期应该是几个小时但实际几乎立即过期。排查发现 src/pages/login/index.vue 第79行调用 oauth2.setOauth({ access_token: accessToken }) 时只传入了access_token，没有传入expires_in字段。而 src/utils/oauth2.js 的setOauth方法第26行用 dayjs().add(oauth.expires_in, 'seconds') 计算过期时间，当expires_in为undefined时，dayjs的add方法返回当前时间本身，导致expires_at被设置为当前时刻。后续isTokenExpired()检查时发现expires_at就是现在，during为0，始终返回true表示已过期。同时Cookies.set()没有传入{expires:N}选项，cookie默认变成session cookie，关闭浏览器也会丢失。需要在login页面传入服务端返回的expires_in，并在setOauth中给Cookie设置合理的过期天数。
