# wrv-login-cred-exposure

## Question ID: l1-095

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: qwen

## Query

安全审计发现登录接口存在凭证暴露风险。auth-center.js 的 getVerifyUser 方法使用 appRequest.get() 发送认证请求，用户名和 MD5 密码以 URL 查询参数形式传输（/api/sysOperator/verifyUser?userName=xxx&password=xxx）。这导致凭证出现在浏览器地址栏历史、服务器访问日志和代理日志中。另外 MD5 作为密码哈希已不安全，存在彩虹表破解风险。需要将登录请求改为 POST 方法，凭证放在请求体中传输，并建议升级哈希算法。