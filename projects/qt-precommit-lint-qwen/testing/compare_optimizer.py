"""
testing/compare_optimizer.py — 等权 vs 组合优化器 蒙特卡洛对比

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/compare_optimizer.py [--sims 20]
"""

from __future__ import annotations

import sys
import random
import argparse
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.data_loader_fast import load_market_data_fast
from live.strategy_account import StrategyAccount
from live.execution_engine_v3 import ExecutionEngine
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.regime_detector_v2 import RegimeDetectorV2
from strategies.factor_strategy import FactorStrategy
from core.portfolio_optimizer import PortfolioOptimizer
from testing.monte_carlo_sim import (
    load_ml_signals,
    random_window,
    gen_sim_id,
    INITIAL_CAPITAL,
    TREND_RATIO,
    LOWVOL_RATIO,
    FACTOR_RATIO,
    CASH_RATIO,
)


def inject_optimizer_weights(
    signals: list[dict],
    account: StrategyAccount,
    prices: dict,
    price_history: dict,
    optimizer: PortfolioOptimizer,
    max_weight: float = 0.20,
) -> list[dict]:
    """
    把优化器权重注入到买入信号的 weight 字段
    卖出信号不变
    """
    # 更新价格历史
    for code, data in prices.items():
        close = data.get("close", 0)
        if close > 0:
            price_history[code].append(close)
            if len(price_history[code]) > 120:
                price_history[code] = price_history[code][-120:]

    buy_codes = [s["ts_code"] for s in signals if s.get("action") == "buy"]
    if not buy_codes:
        return signals

    # 候选股 = 当前持仓 + 新买入
    candidates = list(set(list(account.positions.keys()) + buy_codes))
    valid = [c for c in candidates if len(price_history.get(c, [])) >= 20]

    if len(valid) < 2:
        # 数据不足，等权
        w = {c: 1.0 / len(buy_codes) for c in buy_codes}
    else:
        import pandas as pd

        min_len = min(len(price_history[c]) for c in valid)
        ret_data = {}
        for c in valid:
            p = price_history[c][-min_len:]
            ret_data[c] = [p[i] / p[i - 1] - 1 for i in range(1, len(p))]
        ret_df = pd.DataFrame(ret_data)
        S = ret_df.cov()
        try:
            w_series = optimizer(S)
            w = {c: min(float(w_series.get(c, 1.0 / len(valid))), max_weight) for c in valid}
            # 归一化
            total = sum(w.get(c, 0) for c in buy_codes)
            if total > 0:
                w = {c: w.get(c, 0) / total for c in buy_codes}
            else:
                w = {c: 1.0 / len(buy_codes) for c in buy_codes}
        except Exception:
            w = {c: 1.0 / len(buy_codes) for c in buy_codes}

    # 注入权重
    result = []
    for sig in signals:
        if sig.get("action") == "buy" and sig["ts_code"] in w:
            sig = dict(sig)
            sig["weight"] = w[sig["ts_code"]]
        result.append(sig)
    return result


def run_one(start_date: str, end_date: str, use_optimizer: bool, optimizer_method: str = "rp") -> dict | None:
    """跑一次模拟，返回统计结果"""
    ml_signals = load_ml_signals()
    warmup_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
    market_data = load_market_data_fast(warmup_start, end_date)
    if not market_data:
        return None

    dates = sorted(market_data.keys())
    sim_dates = [d for d in dates if start_date <= d <= end_date]
    warmup_dates = [d for d in dates if d < start_date]
    if len(sim_dates) < 5:
        return None

    trend_acc = StrategyAccount("Trend", INITIAL_CAPITAL * TREND_RATIO)
    lowvol_acc = StrategyAccount("LowVol", INITIAL_CAPITAL * LOWVOL_RATIO)
    factor_acc = StrategyAccount("Factor", INITIAL_CAPITAL * FACTOR_RATIO)

    trend_eng = ExecutionEngine(trend_acc)
    lowvol_eng = ExecutionEngine(lowvol_acc)
    factor_eng = ExecutionEngine(factor_acc)

    trend = TrendStrategyV2()
    lowvol = LowVolStrategy()
    det = RegimeDetectorV2()
    factor = FactorStrategy(factor_scores=ml_signals, top_n=15, rebalance_days=5)

    optimizer = PortfolioOptimizer(method=optimizer_method) if use_optimizer else None
    ph = defaultdict(list)  # price_history

    # 预热
    for date in warmup_dates:
        prices = market_data[date]
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            det.update(np.mean(closes), 0)
        trend.generate(date, prices)
        lowvol.set_regime(det.detect())
        lowvol.generate(date, prices)
        factor.generate(date, prices)
        if use_optimizer:
            for code, data in prices.items():
                if data.get("close", 0) > 0:
                    ph[code].append(data["close"])

    # 模拟
    equity_curve = []
    prev_equity = INITIAL_CAPITAL

    for date in sim_dates:
        prices = market_data[date]
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            det.update(np.mean(closes), 0)
        regime = det.detect()
        lowvol.set_regime(regime)

        ts = trend.generate(date, prices)
        ls = lowvol.generate(date, prices)
        fs = factor.generate(date, prices)

        if regime == "CRISIS":
            ts = [{"action": "sell", "ts_code": c} for c in list(trend_acc.positions)]
            ls = [{"action": "sell", "ts_code": c} for c in list(lowvol_acc.positions)]
            fs = [{"action": "sell", "ts_code": c} for c in list(factor_acc.positions)]
        elif use_optimizer and optimizer:
            ts = inject_optimizer_weights(ts, trend_acc, prices, ph, optimizer)
            ls = inject_optimizer_weights(ls, lowvol_acc, prices, ph, optimizer)
            fs = inject_optimizer_weights(fs, factor_acc, prices, ph, optimizer)

        trend_eng.queue_orders(ts)
        lowvol_eng.queue_orders(ls)
        factor_eng.queue_orders(fs)
        trend_eng.execute(prices, date=date)
        lowvol_eng.execute(prices, date=date)
        factor_eng.execute(prices, date=date)

        trend_acc.mark_to_market(prices)
        lowvol_acc.mark_to_market(prices)
        factor_acc.mark_to_market(prices)

        total_eq = (
            trend_acc.total_equity + lowvol_acc.total_equity + factor_acc.total_equity + INITIAL_CAPITAL * CASH_RATIO
        )
        equity_curve.append(total_eq)
        prev_equity = total_eq

        for acc in [trend_acc, lowvol_acc, factor_acc]:
            acc.trade_log.clear()

    if not equity_curve:
        return None

    eq = np.array(equity_curve)
    total_ret = eq[-1] / INITIAL_CAPITAL - 1
    peak = np.maximum.accumulate(eq)
    dd = np.max((peak - eq) / peak) if peak.max() > 0 else 0
    rets = np.diff(eq) / eq[:-1]
    sharpe = (rets.mean() / rets.std() * np.sqrt(240)) if rets.std() > 0 else 0

    return {"total_return": total_ret, "max_drawdown": dd, "sharpe": sharpe}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sims", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)

    windows = [random_window() for _ in range(args.sims)]
    results = {"equal": [], "rp": [], "inv": []}

    for i, (start, end, months) in enumerate(windows):
        print(f"\n[{i + 1}/{args.sims}] {start} ~ {end} ({months}M)")
        for method in ["equal", "rp", "inv"]:
            use_opt = method != "equal"
            r = run_one(start, end, use_optimizer=use_opt, optimizer_method=method)
            if r:
                results[method].append(r)
                print(
                    f"  {method:6s}: ret={r['total_return']:+.2%}  dd={r['max_drawdown']:.2%}  sharpe={r['sharpe']:.2f}"
                )

    # 汇总报告
    print("\n" + "=" * 60)
    print("  等权 vs 组合优化器 对比结果")
    print("=" * 60)
    print(f"{'方法':8s} {'平均收益':>10s} {'平均回撤':>10s} {'平均Sharpe':>12s} {'胜率':>8s}")
    print("-" * 55)

    equal_rets = [r["total_return"] for r in results["equal"]]
    for method, data in results.items():
        if not data:
            continue
        rets = [r["total_return"] for r in data]
        dds = [r["max_drawdown"] for r in data]
        srs = [r["sharpe"] for r in data]
        win = ""
        if method != "equal" and equal_rets:
            wins = sum(1 for a, b in zip(rets, equal_rets) if a > b)
            win = f"{wins}/{len(rets)}"
        print(f"{method:8s} {np.mean(rets):>+10.2%} {np.mean(dds):>10.2%} {np.mean(srs):>12.2f} {win:>8s}")

    # 保存报告
    report_path = Path("testing/optimizer_compare_report.md")
    with open(report_path, "w") as f:
        f.write(f"# 等权 vs 组合优化器 蒙特卡洛对比\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"模拟次数: {args.sims}\n\n")
        f.write("| 方法 | 平均收益 | 平均回撤 | 平均Sharpe | 胜率 |\n")
        f.write("|------|---------|---------|-----------|------|\n")
        for method, data in results.items():
            if not data:
                continue
            rets = [r["total_return"] for r in data]
            dds = [r["max_drawdown"] for r in data]
            srs = [r["sharpe"] for r in data]
            win = ""
            if method != "equal" and equal_rets:
                wins = sum(1 for a, b in zip(rets, equal_rets) if a > b)
                win = f"{wins}/{len(rets)}"
            f.write(f"| {method} | {np.mean(rets):+.2%} | {np.mean(dds):.2%} | {np.mean(srs):.2f} | {win} |\n")
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
