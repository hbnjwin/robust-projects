# qt-radon-complexity (l1-181)

| Field | Value |
|-------|-------|
| Question ID | l1-181 |
| Task Type | enhancement |
| App Domain | devtools_test |
| Language | python |
| Model | Qwen |

## Query

最近改 live/replay_engine_v3.py 的时候发现 run_backtest 方法快 200 行了，圈复杂度估计得有 30 以上，每次改都怕引入 bug。项目里类似的大函数不少，比如 services/ 下好几个服务的 run 方法、control/scheduler_v2.py 的任务调度逻辑。我想引入 radon 做复杂度分析，建立一个持续监控机制。需要：1) 写一个 scripts/complexity_report.py，用 radon 的 cc（圈复杂度）和 mi（可维护性指数）扫描整个项目，生成一份按严重度排序的 JSON 报告，区分 A/B/C/D/E/F 等级，对 D 及以上标红；2) 在 pyproject.toml 里配置 radon 的阈值参数（建议 cc 阈值 15，mi 阈值 20），并排除 testing/ 和 docs/ 目录；3) 对报告中排名前三的高复杂度函数，做实际的重构降低复杂度——不是简单提取子函数糊弄，要真正理解业务逻辑后做有意义的拆分；4) 写一个 scripts/complexity_gate.py 门禁脚本，新增代码如果引入 cc 超过阈值的函数就非零退出，输出具体哪个函数超标了。
