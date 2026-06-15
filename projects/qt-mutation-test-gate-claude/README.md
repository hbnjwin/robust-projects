# qt-mutation-test-gate (l1-180)

| Field | Value |
|-------|-------|
| Question ID | l1-180 |
| Task Type | enhancement |
| App Domain | devtools_test |
| Language | python |
| Model | Claude |

## Query

项目的 testing/ 目录已经从脚本式测试迁移到了 pytest，但现在没有手段验证这些测试本身的质量——某些测试可能只是跑通了不报错，但实际上对关键逻辑的断言太弱，改了代码测试照样过。我想用 mutmut 做变异测试来检测这个问题。具体需要：1) 安装配置 mutmut，在 setup.cfg 或 pyproject.toml 里定义变异范围，重点覆盖 core/matcher.py（撮合引擎的价格约束和 T+1 规则）、core/risk.py（风控门禁的资金和持仓校验）、analytics/metrics_v2.py（夏普率和最大回撤计算）这三个最核心的模块；2) 写一个 scripts/run_mutation.py 脚本，执行变异测试后解析 mutmut 的 results 生成一份 JSON 报告，包含每个模块的变异得分（killed/total）、存活变异体的具体位置和变异类型；3) 对发现的存活变异体（survived mutants），至少补充 3 个针对性的测试用例消灭它们；4) 写一个 scripts/mutation_gate.py 门禁脚本，如果任何目标模块的变异得分低于 80% 就返回非零退出码，可以接入 CI。
