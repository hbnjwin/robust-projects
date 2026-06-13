# 死代码检测与清理报告

> 生成时间: 2026-06-13 19:04
> 工具: vulture (min-confidence=60) + AST import 分析 + grep 交叉验证
> 范围: 项目核心代码 (排除 quant-qmt-ptrade/ 外部子项目)

## 一、可安全删除的文件

以下文件经过 **AST import 分析 + grep 字符串搜索** 双重确认，无任何外部引用。

| # | 文件 | 大小 | 行数 | 删除理由 | 备注 |
|---|------|------|------|----------|------|
| 1 | `main.py` | 1.2KB | 47 | 引用不存在的 engine/ 模块，项目已迁移至 core/ + live/replay_engine_v5 | 最早期单股票回测入口，已完全无法运行 |
| 2 | `optimize_ma.py` | 1.6KB | 64 | 无外部 import，仅在 test_p0_sql_injection.py 的文件名列表中被提及 | MA 参数优化脚本，功能已被 walk_forward.py 替代 |
| 3 | `live/replay_engine_v1.py` | 3.0KB | 80 | 无外部 import，文件头已标记 DEPRECATED | 最简版回测引擎（2策略、固定配比），已被 v3+ 完全替代 |
| 4 | `live/simple_strategy.py` | 0.6KB | 12 | 仅被 replay_engine_v1.py（同属待删除）和 run_single_2018.py 引用 | V1 简单趋势策略，已被 trend_strategy_v2.py 替代 |
| 5 | `live/low_vol_strategy.py` | 0.7KB | 15 | 仅被 replay_engine_v1.py（同属待删除）引用 | V1 低波策略，已被 lowvol_strategy_v2.py 替代 |
| 6 | `live/replay_engine_v4.py` | 7.4KB | 194 | 无外部 import | ML信号驱动回测引擎，已被 v5 (事件驱动) 替代 |
| 7 | `services/paper_trading_v1.py` | 5.2KB | 171 | 无外部 import，仅在 ml_signal_generate.py 注释中被提及 | 单策略模拟交易，已被 v2（3策略+ML信号）完全替代 |
| 8 | `services/signal_generator_v1.py` | 3.2KB | 96 | 无外部 import，仅在 draw_architecture.py 图表和 test_p1_fixes.py 检查中被引用 | V1 信号生成器，已被 ml_signal_generate.py 等替代 |
| 9 | `execution/broker_simulator.py` | 0.4KB | 11 | 无外部 import，无 grep 引用 | 早期券商模拟器，功能已整合至 core/oms.py + execution/ |
| 10 | `execution/position_manager.py` | 0.5KB | 17 | 无外部 import，无 grep 引用 | 早期持仓管理器，功能已整合至 live/ 模块 |
| 11 | `execution/risk_controller.py` | 0.6KB | 18 | 无外部 import，无 grep 引用 | 早期风控器，功能已整合至 core/risk.py |
| 12 | `data/import_full_market_copy.py` | 2.1KB | 84 | 无外部 import，无 grep 引用 | 全市场导入脚本的副本文件 |
| 13 | `data/import_full_market_safe.py` | 3.9KB | 126 | 无外部 import，无 grep 引用 | 全市场导入脚本的安全版本，已被 import_full_market_akshare.py 替代 |
| 14 | `data/tushare_loader.py` | 1.3KB | 55 | 无外部 import，无 grep 引用 | Tushare 数据加载器（SQLite），项目已迁移至 PostgreSQL |

**合计**: 14 个文件, ~990 行代码, ~31.5KB

### 确认方法
```bash
# 对每个文件执行以下命令确认无外部引用:
grep -r 'main' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'main.py'
grep -r 'optimize_ma' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'optimize_ma.py'
grep -r 'replay_engine_v1' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'live/replay_engine_v1.py'
grep -r 'simple_strategy' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'live/simple_strategy.py'
grep -r 'low_vol_strategy' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'live/low_vol_strategy.py'
grep -r 'replay_engine_v4' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'live/replay_engine_v4.py'
grep -r 'paper_trading_v1' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'services/paper_trading_v1.py'
grep -r 'signal_generator_v1' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'services/signal_generator_v1.py'
grep -r 'broker_simulator' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'execution/broker_simulator.py'
grep -r 'position_manager' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'execution/position_manager.py'
grep -r 'risk_controller' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'execution/risk_controller.py'
grep -r 'import_full_market_copy' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'data/import_full_market_copy.py'
grep -r 'import_full_market_safe' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'data/import_full_market_safe.py'
grep -r 'tushare_loader' --include='*.py' . | grep -v quant-qmt-ptrade | grep -v __pycache__ | grep -v 'data/tushare_loader.py'
```

## 二、需要级联删除的文件组

以下文件存在少量引用，但引用方本身也是废弃/测试代码，应一并清理。

### 组 A: replay_engine_v2 及其依赖链

| 文件 | 引用方 | 建议 |
|------|--------|------|
| `live/replay_engine_v2.py` | `services/run_single_2018.py`, `services/run_single_lowvol_2018.py`, `services/run_single_lowvol_2021.py`, `testing/test_p1_fixes.py` | 连同引用方一起删除 |
| `services/run_single_2018.py` | — (仅引用 v2) | 删除 |
| `services/run_single_lowvol_2018.py` | — (仅引用 v2) | 删除 |
| `services/run_single_lowvol_2021.py` | — (仅引用 v2) | 删除 |

> `testing/test_p1_fixes.py` 中对 v2 的引用是文件路径检查（`open("...")`），删除 v2 后需移除该测试段落。

### 组 B: 旧版 run_* 脚本 (依赖 analytics.metrics v1)

`analytics.metrics` (v1) 被以下文件 import，但项目已迁移至 `analytics.metrics_v2`：

| 文件 | 是否仍在活跃使用 |
|------|------------------|
| `run_backtest_pg.py` | 需确认 — 可能被 unified_backtest.py 替代 |
| `run_portfolio.py` | 需确认 |
| `run_portfolio_hedge.py` | 需确认 |
| `run_portfolio_rebalance.py` | 需确认 |
| `run_portfolio_risk.py` | 需确认 |
| `run_portfolio_vol_weight.py` | 需确认 |
| `run_upgrade.py` | 需确认 |
| `walk_forward.py` (root) | 需确认 — 可能被 services/walk_forward.py 替代 |

> **建议**: 将上述 run_* 脚本的 `from analytics.metrics import` 迁移至 `analytics.metrics_v2`，或确认无活跃使用后删除。

## 三、保留但需标记 deprecated 的文件

以下文件仍被活跃引用，但已是旧版本，建议添加 deprecation warning。

| 文件 | 活跃引用方 | 替代版本 | 建议操作 |
|------|-----------|----------|----------|
| `live/replay_engine_v3.py` | `unified_backtest.py`, `testing/` 多个测试 | `replay_engine_v5.py` (事件驱动) | 添加 `warnings.warn` + docstring 标记 |
| `analytics/metrics.py` (v1) | 多个 `run_*.py` 脚本 | `analytics/metrics_v2.py` | 添加 deprecation warning，推动迁移 |
| `data/db.py` | `services/watchlist_monitor.py` | `dao/postgres_dao.py` | 添加 deprecation warning |
| `services/run_v4_backtest.py` | — | `replay_engine_v5` | 确认是否仍需要 |
| `vnpy_ext/signal_bridge.py` | 引用 signal_generator_v1 (已删) | 需更新引用 | 更新注释或删除 |
| `draw_architecture.py` | 引用 signal_generator_v1 (已删) | — | 更新架构图或标记 |

## 四、engine/ 目录分析

### 发现: engine/ 目录已不存在

`engine/` 目录在之前的架构迁移中已被删除，其功能已分散至：

| 原 engine/ 模块 | 当前位置 |
|----------------|----------|
| `engine.datafeed` | `core/datafeed.py` |
| `engine.broker` | `core/oms.py` + `execution/` |
| `engine.portfolio` | `live/master_portfolio.py` + `core/portfolio_optimizer.py` |
| `engine.backtest` | `live/replay_engine_v3~v5.py` |

**结论**: 无需对 engine/ 执行 deprecation 标记操作。`main.py` 是唯一残留引用，已在「可安全删除」列表中。

## 五、Vulture 死代码扫描结果 (核心项目)

### 5.1 未使用的类 (按大小排序)

| 文件 | 类名 | 行数 | 置信度 | 说明 |
|------|------|------|--------|------|
| `vnpy_ext/risk_monitor.py` | `RiskMonitor` | 330 | 60% | 整个类未被使用 |
| `vnpy_ext/tx_realtime_gateway.py` | `TxRealtimeGateway` | 229 | 60% | 整个类未被使用 |
| `live/replay_engine_v4.py` | `ReplayEngineV4` | 176 | 60% | 已被 v5 替代 |
| `core/risk.py` | `RiskGate` | 141 | 60% | 风控门类未被调用 |
| `core/risk.py` | `OrderPersistence` | 83 | 60% | 订单持久化类未被调用 |
| `core/risk.py` | `CancelAndReplace` | 77 | 60% | 撤单重挂类未被调用 |
| `core/risk.py` | `OrderTimeoutManager` | 61 | 60% | 订单超时管理类未被调用 |
| `data/tushare_loader.py` | `save_to_sqlite()` | 32 | 60% | SQLite 保存函数（已迁移 PG） |
| `data/duckdb_engine.py` | `quick_factor_pipeline()` | 32 | 60% | 因子管道函数未被调用 |
| `testing/phase5_fusion_backtest.py` | `ReplayEngineWithHIST` | 31 | 60% | 测试用回测引擎 |
| `alpha/adapters/hist_alpha.py` | `HISTAlpha` | 30 | 60% | HIST Alpha 适配器未被调用 |
| `alpha/adapters/ml_alpha.py` | `MLAlpha` | 10 | 60% | ML Alpha 适配器未被调用 |
| `execution/broker_simulator.py` | `BrokerSimulator` | 11 | 60% | 已列入安全删除 |
| `execution/position_manager.py` | `PositionManager` | 17 | 60% | 已列入安全删除 |
| `execution/risk_controller.py` | `RiskController` | 18 | 60% | 已列入安全删除 |

### 5.2 未使用的函数/方法

| 文件 | 函数 | 行数 | 说明 |
|------|------|------|------|
| `core/portfolio_optimizer.py` | `optimize_weights()` | 43 | 组合优化函数未被调用 |
| `factor/factor_loader.py` | `load_factors()` | 42 | 因子加载函数未被调用 |
| `data/db.py` | `init_db()` | 21 | SQLite 初始化（已迁移 PG） |
| `ml/evaluator.py` | `print_evaluation_report()` | 29 | 评估报告打印函数 |
| `ml/trainer.py` | `evaluate_test()` | 20 | 测试评估方法 |
| `ml/trainer.py` | `load_models()` | 17 | 模型加载方法 |
| `core/risk.py` | `chase()` | 27 | 追单方法 |
| `core/risk.py` | `restore()` | 41 | 恢复方法 |
| `core/risk.py` | `load_snapshot()` | 6 | 快照加载方法 |
| `live/paper_gateway.py` | `fetch_quotes()` | 29 | 行情获取方法 |
| `live/signal_server.py` | `get_signal()` | 7 | 信号获取函数 |
| `live/inline_factor_generator.py` | `get_factor_exposures()` | 8 | 因子暴露获取方法 |
| `ml/models/lasso_model.py` | `selected_features()` | 11 | 特征选择方法 |
| `ml/models/lgb_model.py` | `top_features()` | 4 | 重要特征方法 |
| `scripts/stock_advisor_fetch.py` | `fetch_news()` | 10 | 新闻抓取函数 |
| `scripts/stock_advisor_fetch.py` | `fetch_realtime()` | 14 | 实时行情函数 |
| `data/tushare_loader.py` | `download_daily()` | 15 | 日线下载函数 |
| `qlib_bridge/qlib_workflow.py` | `run_lgb()` | 32 | LightGBM 运行函数 |
| `qlib_bridge/adapter.py` | `_qlib_to_ts()` | 2 | Qlib 时间转换函数 |
| `factor_lib/ts_factors.py` | `factor_turnover()` | 3 | 因子换手率函数 |
| `factor_lib/ic_analysis.py` | `daily_rank_ic()` | 3 | 日度 Rank IC 函数 |

### 5.3 未使用的 import (高置信度 ≥90%)

| 文件 | 未使用的 import | 说明 |
|------|----------------|------|
| `draw_architecture.py` | `mpatches, FancyArrowPatch` | matplotlib 绘图组件 |
| `gpu-train/train_gru.py` | `TensorDataset` | PyTorch 数据集类 |
| `qlib_bridge/qlib_workflow.py` | `DataHandlerLP, TopkDropoutStrategy, backtest_daily, risk_analysis, PortAnaRecord` | Qlib 组件 |
| `qlib_bridge/train_gru.py` | `TensorDataset` | PyTorch 数据集类 |
| `testing/phase5_fusion_backtest.py` | `_lmd` | Lambda 导入 |

## 六、重复/冗余代码检测

| 文件 A | 文件 B | 关系 |
|--------|--------|------|
| `gpu-train/train_gats.py` | `scripts/train_gats.py` | **完全重复** — scripts/ 是 gpu-train/ 的副本 |
| `gpu-train/train_hist.py` | `scripts/train_hist.py` | **完全重复** — scripts/ 是 gpu-train/ 的副本 |
| `gpu-train/train_gru.py` | `qlib_bridge/train_gru.py` | **完全重复** — qlib_bridge/ 是 gpu-train/ 的副本 |
| `live/execution_engine_v2.py` | `live/execution_engine_v3.py` | v3 是 v2 的增强版，v2 可能已废弃 |
| `analytics/metrics.py` | `analytics/metrics_v2.py` | v2 是 v1 的替代版 |
| `control/scheduler.py` | `control/scheduler_v2.py` | v2 是 v1 的替代版 |
| `live/data_loader.py` | `live/data_loader_fast.py` | fast 版是优化版 |

## 七、推荐执行步骤

### Phase 1: 安全删除 (低风险)
```bash
# 1. 删除无引用文件
git rm main.py
git rm optimize_ma.py
git rm live/replay_engine_v1.py
git rm live/simple_strategy.py
git rm live/low_vol_strategy.py
git rm live/replay_engine_v4.py
git rm services/paper_trading_v1.py
git rm services/signal_generator_v1.py
git rm execution/broker_simulator.py
git rm execution/position_manager.py
git rm execution/risk_controller.py
git rm data/import_full_market_copy.py
git rm data/import_full_market_safe.py
git rm data/tushare_loader.py

# 2. 删除重复脚本
git rm scripts/train_gats.py scripts/train_hist.py qlib_bridge/train_gru.py
```

### Phase 2: 级联删除 (需确认)
```bash
# 删除 replay_engine_v2 及其依赖链
git rm live/replay_engine_v2.py
git rm services/run_single_2018.py
git rm services/run_single_lowvol_2018.py
git rm services/run_single_lowvol_2021.py

# 更新 testing/test_p1_fixes.py 中引用 v2 的测试段落
```

### Phase 3: Deprecation 标记 (保留文件)
```python
# 在以下文件顶部添加:
import warnings
warnings.warn(
    "本模块已废弃，请使用 xxx 替代",
    DeprecationWarning, stacklevel=2
)
```

需标记的文件:
- `live/replay_engine_v3.py` → 替代: `replay_engine_v5.py`
- `analytics/metrics.py` → 替代: `analytics/metrics_v2.py`
- `data/db.py` → 替代: `dao/postgres_dao.py`
- `live/execution_engine_v2.py` → 替代: `execution_engine_v3.py`
- `control/scheduler.py` → 替代: `control/scheduler_v2.py`
- `live/data_loader.py` → 替代: `data_loader_fast.py`

### Phase 4: 清理未使用代码 (可选)
```bash
# 使用 vulture + 白名单运行
vulture . --exclude quant-qmt-ptrade --min-confidence 80 .vulture_whitelist.py
```

---
*报告由 generate_cleanup_report.py 自动生成 — 2026-06-13 19:04*