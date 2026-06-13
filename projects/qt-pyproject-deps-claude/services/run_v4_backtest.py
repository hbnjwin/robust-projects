"""V4 五场景回测"""
import sys, time, json
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.data_loader_fast import load_market_data_fast
from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine
from live.regime_detector_v2 import RegimeDetectorV2
from strategies.factor_strategy import FactorStrategy

SCENARIOS = [
    ("2018-2019 震荡熊", "2018-01-01", "2019-12-31"),
    ("2020-2021 牛市",   "2020-01-01", "2021-12-31"),
    ("2022 熊市",        "2022-01-01", "2022-12-31"),
    ("2023 震荡",        "2023-01-01", "2023-12-31"),
    ("2024-2025 测试集", "2024-01-01", "2025-03-13"),
]

def main():
    # 加载 ML 信号
    t0 = time.time()
    sig_df = pd.read_parquet("data/ml_signals.parquet")
    ml_signals = {}
    for d, g in sig_df.groupby("trade_date"):
        ml_signals[d] = dict(zip(g["ts_code"], g["score"]))
    print(f"Signals: {len(ml_signals)} days in {time.time()-t0:.1f}s")

    capital = 1_000_000
    results = []

    for name, start, end in SCENARIOS:
        print(f"\n--- {name} ({start}~{end}) ---")
        t1 = time.time()
        market_data = load_market_data_fast(start, end)
        print(f"  Data: {len(market_data)} days in {time.time()-t1:.1f}s")

        t2 = time.time()
        acc = StrategyAccount("V4", capital)
        eng = ExecutionEngine(acc)
        det = RegimeDetectorV2()
        strat = FactorStrategy(factor_scores=ml_signals, top_n=15, rebalance_days=5)

        equities = [capital]
        for date in sorted(market_data.keys()):
            prices = market_data[date]
            closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
            if closes:
                det.update(np.mean(closes), 0)
            regime = det.detect()
            signals = strat.generate(date, prices)
            if regime == "CRISIS":
                signals = [{"action": "sell", "ts_code": c} for c in list(acc.positions.keys())]
            eng.queue_orders(signals)
            eng.execute(prices, date=date)
            acc.mark_to_market(prices)
            equities.append(acc.total_equity)

        elapsed = time.time() - t2
        ret = (acc.total_equity / capital - 1) * 100
        dd = acc.max_drawdown * 100
        days = len(market_data)
        annual = ret / days * 240 if days > 0 else 0

        daily_rets = []
        for i in range(1, len(equities)):
            if equities[i - 1] > 0:
                daily_rets.append((equities[i] - equities[i - 1]) / equities[i - 1])
        if len(daily_rets) > 1 and np.std(daily_rets) > 0:
            sharpe = float(np.mean(daily_rets) / np.std(daily_rets) * np.sqrt(240))
        else:
            sharpe = 0.0

        results.append({
            "scenario": name,
            "return": round(ret, 2),
            "annual": round(annual, 2),
            "max_dd": round(dd, 2),
            "sharpe": round(sharpe, 2),
            "final_equity": round(acc.total_equity, 0),
            "time": round(elapsed, 1),
        })
        print(f"  V4: ret={ret:+.2f}% annual={annual:+.2f}% dd={dd:.2f}% sharpe={sharpe:.2f} ({elapsed:.1f}s)")

    # 汇总
    print(f"\n{'='*70}")
    print(f"  V4 (ML LightGBM) 五场景回测结果")
    print(f"{'='*70}")
    print(f"{'场景':<20} {'收益%':>10} {'年化%':>10} {'回撤%':>10} {'Sharpe':>10}")
    print(f"{'─'*60}")
    for r in results:
        print(f"{r['scenario']:<20} {r['return']:>+10.2f} {r['annual']:>+10.2f} {r['max_dd']:>10.2f} {r['sharpe']:>10.2f}")
    print(f"{'─'*60}")

    with open("data/v4_backtest_results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Saved to data/v4_backtest_results.json")

if __name__ == "__main__":
    main()
