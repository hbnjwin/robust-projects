"""
V3 vs V4 Factor策略对比回测 (精简版)
只对比 Factor 策略部分: InlineFactorGenerator vs ML信号
绕过 V3 的 PG 指数加载瓶颈

用法:
    cd /home/tulin/quant
    python services/run_ml_backtest.py
"""

import sys
import time
import json
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.data_loader_fast import load_market_data_fast
from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine
from live.regime_detector_v2 import RegimeDetectorV2
from live.inline_factor_generator import InlineFactorGenerator
from live.adaptive_config import AdaptiveConfig
from strategies.factor_strategy import FactorStrategy


SCENARIOS = [
    ("2018-2019 震荡熊", "2018-01-01", "2019-12-31"),
    ("2020-2021 牛市", "2020-01-01", "2021-12-31"),
    ("2022 熊市", "2022-01-01", "2022-12-31"),
    ("2023 震荡", "2023-01-01", "2023-12-31"),
    ("2024-2025 测试集", "2024-01-01", "2025-03-13"),
]


def load_ml_signals(path: str = "data/ml_signals.parquet") -> dict:
    df = pd.read_parquet(path)
    signals = {}
    for date_str, group in df.groupby("trade_date"):
        signals[date_str] = dict(zip(group["ts_code"], group["score"]))
    return signals


def run_factor_backtest(market_data, ml_signals=None, top_n=15, rebalance_days=5, capital=1_000_000):
    """
    运行单策略回测 (Factor only)
    ml_signals=None → 用 InlineFactorGenerator (V3规则)
    ml_signals=dict → 用 ML信号 (V4)
    """
    account = StrategyAccount("Factor", capital)
    engine = ExecutionEngine(account)
    regime_detector = RegimeDetectorV2()

    if ml_signals is not None:
        # V4: ML信号驱动
        strategy = FactorStrategy(factor_scores=ml_signals, top_n=top_n, rebalance_days=rebalance_days)
        factor_gen = None
    else:
        # V3: 规则驱动
        factor_gen = InlineFactorGenerator()
        strategy = FactorStrategy(factor_scores={}, top_n=top_n, rebalance_days=rebalance_days)

    dates = sorted(market_data.keys())
    for date in dates:
        prices = market_data[date]

        # Regime 检测 (全市场均价代理)
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            regime_detector.update(np.mean(closes), 0)
        regime = regime_detector.detect()

        if factor_gen is not None:
            # V3: 实时计算因子
            adaptive_cfg = AdaptiveConfig.get_config(regime)
            factor_gen.set_regime(regime)
            factor_gen.update(prices)
            scores = factor_gen.compute_scores()
            strategy.factor_scores[date] = scores

        signals = strategy.generate(date, prices)

        # Crisis: 清仓
        if regime == "CRISIS":
            signals = [{"action": "sell", "ts_code": code} for code in list(account.positions.keys())]

        engine.queue_orders(signals)
        engine.execute(prices, date=date)
        account.mark_to_market(prices)
        account.record(date)

    return account.equity_curve


def calc_stats(curve, capital=1_000_000):
    if not curve or len(curve) < 2:
        return {"return": 0, "annual": 0, "dd": 0, "sharpe": 0, "days": 0}

    equities = [p["equity"] for p in curve]
    final = equities[-1]
    total_ret = (final / capital - 1) * 100
    days = len(curve)
    annual = total_ret / days * 240 if days > 0 else 0
    dd = max(p["drawdown"] for p in curve) * 100

    rets = []
    for i in range(1, len(equities)):
        if equities[i - 1] > 0:
            rets.append((equities[i] - equities[i - 1]) / equities[i - 1])
    if len(rets) > 1:
        sharpe = float(np.mean(rets) / np.std(rets) * np.sqrt(240)) if np.std(rets) > 0 else 0
    else:
        sharpe = 0

    return {
        "return": round(total_ret, 2),
        "annual": round(annual, 2),
        "dd": round(dd, 2),
        "sharpe": round(sharpe, 2),
        "days": days,
        "final": round(final, 0),
    }


def main():
    print("=" * 80)
    print("  Factor策略对比: V3 (InlineFactorGenerator) vs V4 (ML LightGBM)")
    print("=" * 80)

    # 加载 ML 信号
    t0 = time.time()
    ml_signals = load_ml_signals()
    print(f"ML signals: {len(ml_signals)} days loaded in {time.time() - t0:.1f}s\n")

    results = []

    for name, start, end in SCENARIOS:
        print(f"{'─' * 70}")
        print(f"  {name} ({start} ~ {end})")
        print(f"{'─' * 70}")

        t1 = time.time()
        market_data = load_market_data_fast(start, end)
        load_time = time.time() - t1
        print(f"  Data: {len(market_data)} days loaded in {load_time:.1f}s")

        # V3: 规则驱动
        t2 = time.time()
        v3_curve = run_factor_backtest(market_data, ml_signals=None)
        v3_time = time.time() - t2
        v3 = calc_stats(v3_curve)

        # V4: ML驱动
        t3 = time.time()
        v4_curve = run_factor_backtest(market_data, ml_signals=ml_signals)
        v4_time = time.time() - t3
        v4 = calc_stats(v4_curve)

        delta = v4["return"] - v3["return"]
        results.append({"scenario": name, "v3": v3, "v4": v4, "delta": delta})

        print(
            f"  V3: ret={v3['return']:+.2f}% annual={v3['annual']:+.2f}% dd={v3['dd']:.2f}% sharpe={v3['sharpe']:.2f} ({v3_time:.1f}s)"
        )
        print(
            f"  V4: ret={v4['return']:+.2f}% annual={v4['annual']:+.2f}% dd={v4['dd']:.2f}% sharpe={v4['sharpe']:.2f} ({v4_time:.1f}s)"
        )
        print(f"  ML增益: {delta:+.2f}%\n")

    # 汇总
    print(f"\n{'=' * 80}")
    print(f"  汇总对比")
    print(f"{'=' * 80}")
    print(
        f"{'场景':<20} {'V3收益%':>10} {'V4收益%':>10} {'增益%':>8} {'V3回撤%':>10} {'V4回撤%':>10} {'V3 Sharpe':>10} {'V4 Sharpe':>10}"
    )
    print(f"{'─' * 88}")

    for r in results:
        v3, v4 = r["v3"], r["v4"]
        print(
            f"{r['scenario']:<20} {v3['return']:>+10.2f} {v4['return']:>+10.2f} {r['delta']:>+8.2f} "
            f"{v3['dd']:>10.2f} {v4['dd']:>10.2f} {v3['sharpe']:>10.2f} {v4['sharpe']:>10.2f}"
        )

    print(f"{'─' * 88}")

    with open("data/v3_vs_v4_backtest_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to data/v3_vs_v4_backtest_results.json")


if __name__ == "__main__":
    main()
