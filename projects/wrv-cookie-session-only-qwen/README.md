# wrv-cookie-session-only

## Question ID: l1-127
## Task Type: bug-fix
## App Domain: web_frontend
## Language: js
## Model: qwen

## Query

用户反馈每次关闭浏览器后重新打开页面都需要重新登录，即使选择了"记住我"或者token尚未过期。排查 src/utils/oauth2.js 第28行的Cookies.set(KEY, JSON.stringify(temp))发现，调用js-cookie的set方法时没有传入第三个参数{expires: N}来设置cookie的过期天数。根据js-cookie文档和HTTP cookie规范，不设置expires/max-age的cookie默认是session cookie，浏览器关闭时自动清除。即使setOauth正确计算了expires_at字段（记录了token的逻辑过期时间），cookie本身在浏览器关闭时就被删除了，用户重新打开浏览器时getOauth()返回空字符串，被路由守卫判定为未登录。需要根据token的有效期给Cookies.set传入合理的expires值，如{expires: oauth.expires_in / 86400}将秒转换为天数。
