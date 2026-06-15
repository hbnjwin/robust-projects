# qt-import-lint-layer (l1-184)

| Field | Value |
|-------|-------|
| Question ID | l1-184 |
| Task Type | enhancement |
| App Domain | devtools_test |
| Language | python |
| Model | Qwen |

## Query

项目到处都是 sys.path.insert(0, ...) 来解决 import 问题，模块之间的依赖关系完全靠人脑记，上次改 core/matcher.py 不小心 import 了 live/ 里的东西差点搞出循环引用。我想用 import-linter 建立分层架构约束。需要：1) 先写一个 scripts/analyze_imports.py 用 AST 解析扫描整个项目的 import 语句，生成依赖图的 JSON 表示（节点是模块，边是 import 关系），统计每个模块的入度出度，列出所有循环依赖链；2) 在 pyproject.toml 或 .importlinter 配置文件里定义分层规则——底层 dao/config → 中层 core/factor_lib/alpha → 上层 strategies/live/ml → 顶层 services/control，约束只允许上层 import 下层不允许反向引用；3) 对 import-linter 报告出的违规项，修复其中最关键的 3 处——把被错误引用的功能下沉到正确的层级或通过接口解耦；4) 清理至少 5 处 sys.path.insert hack，改为使用相对导入或在项目根目录配置 PYTHONPATH，确保清理后所有测试仍能通过。
