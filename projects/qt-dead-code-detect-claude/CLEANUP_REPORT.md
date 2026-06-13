# Dead Code Detection & Cleanup Report

**Project**: qt-dead-code-detect-claude (Quant Trading Platform)
**Date**: 2026-06-13
**Tool**: vulture 2.16 (--min-confidence 60)

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Vulture raw findings | 519 |
| False positives whitelisted | 229 |
| Remaining genuine findings | 290 |
| Main project findings (excl. quant-qmt-ptrade) | 93 |
| Files safe to delete | 11 |
| Files to mark DEPRECATED | 13 |
| engine/ files with deprecation warning added | 4 + __init__.py |

---

## Part 1: Files Safe to Delete

These files have **zero importers** across the entire project. Confirmation commands provided.

### 1.1 Completely Dead Files (zero references)

| # | File | Reason | Confirmation Command |
|---|------|--------|---------------------|
| 1 | `services/generate_daily_report_v1.py` | Zero references in entire project | `grep -r "generate_daily_report" --include="*.py" .` |
| 2 | `services/stability_monitor_v1.py` | Zero imports; only a diagram label in draw_architecture.py | `grep -r "stability_monitor_v1" --include="*.py" .` |
| 3 | `control/scheduler.py` | Zero importers; root scheduler.py is separate | `grep -r "from control.scheduler " --include="*.py" .` |
| 4 | `control/scheduler_v2.py` | Zero importers; only read by test_p1_fixes.py for file validation | `grep -r "from control.scheduler_v2" --include="*.py" .` |

### 1.2 Deprecated Files with No Active Consumers

| # | File | Reason | Confirmation Command |
|---|------|--------|---------------------|
| 5 | `live/replay_engine_v1.py` | Explicitly DEPRECATED in header; zero importers | `grep -r "replay_engine_v1" --include="*.py" .` |
| 6 | `live/low_vol_strategy.py` | Explicitly DEPRECATED; only imported by replay_engine_v1 (also dead) | `grep -r "low_vol_strategy" --include="*.py" .` |
| 7 | `services/paper_trading_v1.py` | Superseded by paper_trading_v2.py; zero importers | `grep -r "paper_trading_v1" --include="*.py" .` |
| 8 | `services/signal_generator_v1.py` | Superseded by signals/signal_generator.py; zero importers | `grep -r "signal_generator_v1" --include="*.py" .` |

### 1.3 Files Safe to Delete After Confirming Cascade

| # | File | Reason | Blocker | Confirmation |
|---|------|--------|---------|-------------|
| 9 | `live/simple_strategy.py` | DEPRECATED; imported by replay_engine_v1 + run_single_2018 | Delete after removing replay_engine_v1; update run_single_2018 to use trend_strategy_v2 | `grep -r "simple_strategy" --include="*.py" .` |
| 10 | `services/run_single_2018.py` | Uses deprecated replay_engine_v2 + simple_strategy | Standalone test script, no importers | `grep -r "run_single_2018" --include="*.py" .` |
| 11 | `services/run_single_lowvol_2018.py` | Uses deprecated replay_engine_v2 | Standalone test script, no importers | `grep -r "run_single_lowvol_2018" --include="*.py" .` |

### Recommended Deletion Order

```bash
# Step 1: Delete files with zero dependencies (safe immediately)
rm services/generate_daily_report_v1.py
rm services/stability_monitor_v1.py
rm control/scheduler.py
rm control/scheduler_v2.py
rm services/paper_trading_v1.py
rm services/signal_generator_v1.py

# Step 2: Delete deprecated live/ cluster
rm live/replay_engine_v1.py
rm live/low_vol_strategy.py

# Step 3: Delete after confirming run_single_2018 is not needed
rm live/simple_strategy.py
rm services/run_single_2018.py
rm services/run_single_lowvol_2018.py
```

---

## Part 2: Files to Keep but Mark DEPRECATED

### 2.1 engine/ Directory (already processed)

**Location**: `quant-qmt-ptrade/services/quant/engine/`

**Status**: Deprecation warnings added to all 4 files; `__init__.py` created with `__all__ = []`.

**Import dependency analysis**:
- 18 files import from engine/ (10 root-level + 8 mirrored in quant-qmt-ptrade)
- ALL are old-style single-backtest runners (main.py, run_backtest_pg.py, run_portfolio*.py, etc.)
- No newer code (replay_engine_v3/v4/v5, unified_backtest.py) uses engine/
- Every file that imports engine/ also imports analytics/metrics.py (the v1 metrics)

**Files that import engine/ (candidates for migration to unified_backtest.py)**:

| File | Purpose |
|------|---------|
| `main.py` | Original single-stock backtest entry (603019.SH, SQLite) |
| `run_backtest_pg.py` | Single-stock backtest (PostgreSQL) |
| `optimize_ma.py` | MA parameter optimization |
| `run_portfolio.py` | Multi-stock equal-weight portfolio |
| `run_portfolio_hedge.py` | Hedged portfolio with index |
| `run_portfolio_rebalance.py` | Monthly rebalance portfolio |
| `run_portfolio_risk.py` | Risk-controlled portfolio |
| `run_portfolio_vol_weight.py` | Volatility-weighted portfolio |
| `run_upgrade.py` | Migration test: engine -> ReplayEngine v2 |
| `walk_forward.py` | Walk-forward validation |

**Recommendation**: These 10 files should be migrated to use `unified_backtest.py` + `ReplayEngineV5`, then the engine/ directory can be fully removed.

### 2.2 analytics/metrics.py

- Superseded by `analytics/metrics_v2.py`
- Still imported by the same 10 old backtest runners (same files as engine/)
- metrics_v2 adds `sharpe_ratio` and is used by all newer code (unified_backtest, testing/)
- **Action**: Mark deprecated; will be removable once old backtest runners are migrated

### 2.3 live/replay_engine_v2.py

- Used by `services/run_single_2018.py` and `services/run_single_lowvol_2018.py`
- Superseded by v3 -> v4 -> v5
- **Action**: Mark deprecated; removable after deleting run_single_*_2018.py

### 2.4 live/replay_engine_v4.py

- Vulture reports `ReplayEngineV4` class as unused (60% confidence)
- Superseded by v5 (event-driven architecture)
- **Action**: Verify no scripts reference it directly, then mark deprecated

```bash
# Verify replay_engine_v4 usage:
grep -r "replay_engine_v4\|ReplayEngineV4" --include="*.py" .
```

### 2.5 control/notification_bridge.py

- Not imported by any file in the main project
- May be used externally; verify before deletion

```bash
grep -r "notification_bridge" --include="*.py" .
```

---

## Part 3: Vulture Dead Code Findings (Main Project, After Whitelist)

93 genuine findings organized by module. Items marked with [*] are in deprecated files.

### core/ (14 findings) -- infrastructure layer, review carefully

```
core/contract.py:27       unused variable 'min_volume'
core/contract.py:77       unused method 'reload'
core/datafeed.py:44       unused method 'load_tick_data'
core/portfolio_optimizer.py:220  unused function 'optimize_weights'
core/risk.py:42            unused class 'RiskGate'
core/risk.py:73            unused method 'update_prices'
core/risk.py:178           unused method 'get_blocked_log'
core/risk.py:181           unused method 'clear_blocked_log'
core/risk.py:189           unused class 'OrderTimeoutManager'
core/risk.py:256           unused class 'CancelAndReplace'
core/risk.py:306           unused method 'chase'
core/risk.py:339           unused class 'OrderPersistence'
core/risk.py:374           unused method 'restore'
core/risk.py:416           unused method 'load_snapshot'
```

**Note**: core/risk.py has 3 entire classes flagged (RiskGate, OrderTimeoutManager, CancelAndReplace, OrderPersistence). These may be pre-built for future live-trading features. Confirm with team before removing.

### execution/ (3 findings) -- entire module appears unused

```
execution/broker_simulator.py:1   unused class 'BrokerSimulator'
execution/position_manager.py:1   unused class 'PositionManager'
execution/risk_controller.py:1    unused class 'RiskController'
```

**Note**: All 3 classes in execution/ are unused. This module may be a planned-but-unconnected replacement for engine/. Verify intent before removing.

### data/ (4 findings)

```
data/db.py:12              unused function 'init_db'
data/duckdb_engine.py:187  unused function 'quick_factor_pipeline'
data/tushare_loader.py:7   unused function 'download_daily'
data/tushare_loader.py:24  unused function 'save_to_sqlite'
```

### live/ (6 findings)

```
live/inline_factor_generator.py:436  unused method 'get_factor_exposures'
live/live_engine.py:368              unused variable 'order_data'     (100%)
live/live_engine.py:372              unused variable 'trade_data'     (100%)
live/live_engine.py:376              unused variable 'account_data'   (100%)
live/paper_gateway.py:122            unused method 'fetch_quotes'
live/replay_engine_v4.py:19         unused class 'ReplayEngineV4'   [*]
live/signal_server.py:29             unused function 'get_signal'
```

### ml/ (5 findings)

```
ml/evaluator.py:88         unused function 'print_evaluation_report'
ml/models/lasso_model.py:90 unused method 'selected_features'
ml/models/lgb_model.py:126  unused method 'top_features'
ml/trainer.py:169           unused method 'load_models'
ml/trainer.py:187           unused method 'evaluate_test'
```

### alpha/ (2 findings)

```
alpha/adapters/hist_alpha.py:13  unused class 'HISTAlpha'
alpha/adapters/ml_alpha.py:14    unused class 'MLAlpha'
```

### factor/ & factor_lib/ (3 findings)

```
factor/factor_loader.py:19       unused function 'load_factors'
factor_lib/ic_analysis.py:50     unused method 'daily_rank_ic'
factor_lib/ts_factors.py:176     unused function 'factor_turnover'
```

### vnpy_ext/ (14 findings)

```
vnpy_ext/pg_daily_gateway.py:56   unused variable 'default_name'
vnpy_ext/pg_daily_gateway.py:64   unused variable 'exchanges'
vnpy_ext/pg_daily_gateway.py:199  unused method 'query_history'
vnpy_ext/pg_daily_gateway.py:242  unused method 'query_position'
vnpy_ext/risk_monitor.py:39       unused class 'RiskMonitor'
vnpy_ext/risk_monitor.py:72       unused attr 'consecutive_loss_days'
vnpy_ext/risk_monitor.py:103      unused variable 'details'        (100%)
vnpy_ext/risk_monitor.py:212      unused method 'check_order_allowed'
vnpy_ext/risk_monitor.py:235      unused method 'reset_daily'
vnpy_ext/risk_monitor.py:304      unused method 'save_daily_snapshot'
vnpy_ext/tx_realtime_gateway.py:36   unused var 'TX_PREFIX_TO_EXCHANGE'
vnpy_ext/tx_realtime_gateway.py:103  unused class 'TxRealtimeGateway'
vnpy_ext/tx_realtime_gateway.py:149  unused method 'subscribe_batch'
vnpy_ext/tx_realtime_gateway.py:156  unused method 'start_polling'
```

**Note**: vnpy_ext classes (RiskMonitor, TxRealtimeGateway) may be used by vnpy framework via dynamic registration. Confirm before removing. The `default_name` / `exchanges` variables are vnpy gateway protocol attributes.

### qlib_bridge/ (7 findings)

```
qlib_bridge/adapter.py:46       unused function '_qlib_to_ts'
qlib_bridge/qlib_workflow.py:18  unused import 'DataHandlerLP'    (90%)
qlib_bridge/qlib_workflow.py:21  unused import 'TopkDropoutStrategy' (90%)
qlib_bridge/qlib_workflow.py:22  unused import 'backtest_daily'   (90%)
qlib_bridge/qlib_workflow.py:22  unused import 'risk_analysis'    (90%)
qlib_bridge/qlib_workflow.py:25  unused import 'PortAnaRecord'    (90%)
qlib_bridge/qlib_workflow.py:109 unused function 'run_lgb'
qlib_bridge/qlib_workflow.py:194 unused variable 'gru_rec'
qlib_bridge/train_gru.py:26     unused import 'TensorDataset'    (90%)
qlib_bridge/train_gru.py:197    unused variable 'test_idx'
```

### Other scattered findings

```
draw_architecture.py:5     unused import 'mpatches'         (90%)
draw_architecture.py:6     unused import 'FancyArrowPatch'  (90%)
run_portfolio_hedge.py:14  unused variable 'INDEX'
run_portfolio_hedge.py:56  unused variable 'idx_df'
walk_forward.py:58         unused variable 'train_ann'
gpu-train/train_gats.py:31 unused variable 'DAILY_BATCH'
gpu-train/train_gats.py:44 unused function 'load_split'
gpu-train/train_gru.py:26  unused import 'TensorDataset'   (90%)
gpu-train/train_gru.py:197 unused variable 'test_idx'
gpu-train/win_gpu_common.py:90 unused function 'assign_time_split'
scripts/stock_advisor_fetch.py:185 unused function 'fetch_realtime'
scripts/stock_advisor_fetch.py:201 unused function 'fetch_news'
testing/phase5_fusion_backtest.py:62 unused class 'ReplayEngineWithHIST'
testing/phase5_fusion_backtest.py:112 unused function 'patched_run'
testing/phase5_fusion_backtest.py:183 unused import '_lmd' (90%)
```

---

## Part 4: Batch Verification Script

Run this script to verify all safe-to-delete files have no external references:

```bash
#!/bin/bash
echo "=== Dead Code Reference Check ==="
echo ""

files=(
  "generate_daily_report_v1"
  "stability_monitor_v1"
  "from control.scheduler "
  "from control.scheduler_v2"
  "replay_engine_v1"
  "low_vol_strategy"
  "paper_trading_v1"
  "signal_generator_v1"
  "simple_strategy"
  "run_single_2018"
  "run_single_lowvol_2018"
)

for pattern in "${files[@]}"; do
  count=$(grep -r "$pattern" --include="*.py" . 2>/dev/null | \
          grep -v "^Binary" | grep -v "__pycache__" | wc -l)
  if [ "$count" -gt 0 ]; then
    echo "[WARN] '$pattern' has $count references:"
    grep -rn "$pattern" --include="*.py" . 2>/dev/null | \
      grep -v "__pycache__" | head -5
  else
    echo "[ OK ] '$pattern' -- zero references, safe to delete"
  fi
  echo ""
done
```

---

## Part 5: Files Produced by This Analysis

| File | Description |
|------|-------------|
| `vulture_raw_report.txt` | Raw vulture output (519 findings) |
| `.vulture_whitelist.py` | Whitelist of 229 false positives (framework hooks, SDK attrs, etc.) |
| `CLEANUP_REPORT.md` | This report |
| `engine/__init__.py` | Created with `__all__ = []` and deprecation docstring |
| `engine/backtest.py` | Deprecation warning added |
| `engine/broker.py` | Deprecation warning added |
| `engine/datafeed.py` | Deprecation warning added |
| `engine/portfolio.py` | Deprecation warning added |

---

## Part 6: Recommended Cleanup Roadmap

### Phase 1 -- Immediate (no risk)
- Delete 6 files with zero references (generate_daily_report_v1, stability_monitor_v1, control/scheduler*, paper_trading_v1, signal_generator_v1)
- Delete live/replay_engine_v1.py + live/low_vol_strategy.py
- Clean unused imports flagged at 90% confidence (draw_architecture.py, gpu-train/train_gru.py, qlib_bridge/)

### Phase 2 -- Low risk (verify first)
- Delete services/run_single_2018.py, run_single_lowvol_2018.py, live/simple_strategy.py
- Mark live/replay_engine_v2.py, live/replay_engine_v4.py as DEPRECATED
- Review execution/ module -- 3 classes appear entirely unused

### Phase 3 -- Migration (requires code changes)
- Migrate 10 old backtest runners from engine/ + analytics/metrics.py to unified_backtest.py + metrics_v2
- After migration, delete engine/ directory entirely
- Remove analytics/metrics.py after all consumers migrated

### Phase 4 -- Deep cleanup
- Address 93 remaining vulture findings in main project
- Priority: 100%-confidence unused variables in live/live_engine.py and vnpy_ext/risk_monitor.py
- Review core/risk.py -- 4 classes may be pre-built for future use; confirm with team
