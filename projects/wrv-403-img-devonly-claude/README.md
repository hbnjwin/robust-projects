# wrv-403-img-devonly

## Question ID: l1-133

## Task Type: bug-fix

## App Domain: web_frontend

## Language: js

## Model: claude

## Query

403 无权限页面在本地开发环境（npm run dev）显示正常，有一张 SVG 错误提示图片占据页面主体区域。但部署到测试环境后，同一个页面只显示一个裂图图标，图片加载失败返回 404。其他页面的图片（如登录页 logo、导航栏头像）在生产环境都能正常显示。
