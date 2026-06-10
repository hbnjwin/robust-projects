# Go API网关限流令牌桶修复
- **题目ID**: l1-220
- **项目**: hak-go-ratelimit-burst
- **模型**: claude
- **技术栈**: Go / gin / rate limiting

## 题面
Go API网关令牌桶限流：突发流量误杀正常请求+全局限流无用户隔离+缺少Retry-After header
