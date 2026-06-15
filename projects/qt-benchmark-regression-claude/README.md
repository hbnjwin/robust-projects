# qt-benchmark-regression (l1-183)

| Field | Value |
|-------|-------|
| Question ID | l1-183 |
| Task Type | enhancement |
| App Domain | devtools_test |
| Language | python |
| Model | Claude |

## Query

项目做了 cProfile 分析但那只是一次性的，没有办法追踪性能是不是在退化。我想用 pytest-benchmark 建一套持续的性能基准测试。需要：1) 在 testing/ 下新建 test_benchmarks.py，对四个性能敏感的路径写 benchmark 测试——ReplayEngineV3.run_backtest 跑 30 天 50 只股票的模拟、DailyMatcher.match 处理 100 笔订单的撮合、PortfolioOptimizer.optimize 对 20 只股票做风险平价优化、factor_lib/ts_factors.py 里的 rolling_sharpe 对 1000 行数据的计算；2) 配置 pytest-benchmark 的 JSON 输出保存到 .benchmarks/ 目录，配置 --benchmark-compare 和 --benchmark-autosave 让每次运行自动和上次比较；3) 写一个 scripts/benchmark_check.py 对比两次 benchmark 结果，如果任何测试的 mean 时间退化超过 20% 就报警（非零退出码），输出退化的具体项和百分比；4) 在 conftest.py 里加一个 pytest marker @pytest.mark.benchmark_suite 方便单独跑性能测试不影响普通 pytest 流程。
