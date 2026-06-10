# ECharts resize事件泄漏

- **题目ID**: l1-209
- **项目**: hak-echart-bindresize
- **模型**: qwen
- **任务类型**: bug-fix / feature / enhancement
- **技术栈**: Vue3 + TypeScript + Element Plus

## 题面

ECharts resize事件未清理导致内存泄漏+keep-alive生命周期管理

## 项目结构

```
src/
├── components/    # 组件
├── composables/   # 组合式函数
├── types/         # 类型定义
└── utils/         # 工具函数
```
