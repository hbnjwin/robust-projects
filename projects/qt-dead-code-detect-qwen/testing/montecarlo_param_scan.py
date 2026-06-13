"""
Monte Carlo 参数鲁棒区间扫描
扫描 Factor 策略的三个关键参数：
  - top_n: 持仓数量
  - rebalance_days: 调仓周期
  - hist_weight: HIST 信号权重（0 = 纯 Factor，0.6 = Factor0.4+HIST0.6）

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/montecarlo_param_scan.py
"""
import sys, os, json, time
from pathlib import Path
from datetime import date
from itertools import product

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 配置 ──────────────────────────────────────────────────────
BACKTEST_START = "2024-07-01"
BACKTEST_END   = "2025-12-31"
INITIAL_CAP    = 1_000_000.0
COST_RATE      = 0.002
MMAP_DIR       = "/vol1/mmap_cache/hist_bt"
OUT_PATH       = _ROOT / "data/backtest_compare/param_scan_results.json"
os.makedirs(OUT_PATH.parent, exist_ok=True)

# ── 参数扫描范围 ──────────────────────────────────────────────
PARAM_GRID = {
    "top_n":          [5, 10, 15, 20, 30],
    "rebalance_days": [5, 10, 15, 20, 30],
    "hist_weight":    [0.0, 0.3, 0.5, 0.6, 0.8],
}

# ── 加载预计算信号 ────────────────────────────────────────────
print("加载预计算信号矩阵 ...")
bt_dates     = np.load(f"{MMAP_DIR}/bt_dates.npy", allow_pickle=True)
hist_mat     = np.load(f"{MMAP_DIR}/hist_signals.npy")
factor_mat   = np.load(f"{MMAP_DIR}/factor_signals.npy")

# 加载股票列表
df_meta = pd.read_parquet(str(_ROOT / "data/factors_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 3, 1)),
             ("trade_date", "<=", date(2025, 12, 31))],
    columns=["ts_code"])
all_stocks = sorted(df_meta["ts_code"].unique())
N_STOCKS   = len(all_stocks)

# 过滤回测区间
trade_dates = [pd.Timestamp(str(d)) for d in bt_dates
               if BACKTEST_START <= str(d) <= BACKTEST_END]
N_DATES = len(trade_dates)
date2di = {str(d): i for i, d in enumerate(bt_dates)}
date_strs = [d.strftime("%Y-%m-%d") for d in trade_dates]

# 截取回测区间的信号矩阵
hist_bt   = np.array([hist_mat[date2di[d]]   for d in date_strs])
factor_bt = np.array([factor_mat[date2di[d]] for d in date_strs])

# 加载价格数据
print("加载价格数据 ...")
price_df = pd.read_parquet(str(_ROOT / "data/daily_price_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 7, 1)),
             ("trade_date", "<=", date(2025, 12, 31))],
    columns=["ts_code", "trade_date", "close"])
price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
price_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close")
print(f"  价格: {price_pivot.shape}")
print(f"  回测交易日: {N_DATES}")


# ── Rank 标准化 ───────────────────────────────────────────────
def rank_normalize(mat):
    result = np.full_like(mat, np.nan)
    for di in range(mat.shape[0]):
        row = mat[di]
        valid = ~np.isnan(row)
        if valid.sum() < 2:
            continue
        ranks = np.argsort(np.argsort(row[valid]))
        result[di, np.where(valid)[0]] = ranks / (valid.sum() - 1)
    return result

print("预计算 Rank 标准化信号 ...")
hist_rank   = rank_normalize(hist_bt)
factor_rank = rank_normalize(factor_bt)
print("  完成")


# ── 单次回测 ─────────────────────────────────────────────────
def run_backtest(signals, top_n, rebalance_days):
    cash = INITIAL_CAP
    positions = {}
    equity_curve = [INITIAL_CAP]

    for di, td in enumerate(trade_dates):
        sig = signals[di]
        valid = ~np.isnan(sig)

        if td in price_pivot.index:
            prices_row = price_pivot.loc[td]
        else:
            prices_row = None

        def get_price(code):
            if prices_row is not None and code in prices_row.index:
                p = prices_row[code]
                return float(p) if not np.isnan(p) else 0.0
            return 0.0

        # mark-to-market
        total_eq = cash
        for si, pos in positions.items():
            p = get_price(all_stocks[si])
            total_eq += pos["shares"] * (p if p > 0 else pos["cost"])

        # 再平衡
        if di % rebalance_days == 0 and valid.sum() > 0:
            valid_idxs = np.where(valid)[0]
            top_local  = np.argsort(sig[valid_idxs])[::-1][:top_n]
            top_global = set(valid_idxs[top_local].tolist())

            for si in list(positions.keys()):
                if si not in top_global:
                    p = get_price(all_stocks[si])
                    if p > 0:
                        cash += positions[si]["shares"] * p * (1 - COST_RATE)
                    del positions[si]

            alloc = total_eq / top_n
            for si in top_global:
                if si not in positions:
                    p = get_price(all_stocks[si])
                    if p <= 0:
                        continue
                    shares = (alloc / p // 100) * 100
                    if shares <= 0:
                        continue
                    cost = shares * p * (1 + COST_RATE)
                    if cost > cash:
                        continue
                    cash -= cost
                    positions[si] = {"shares": shares, "cost": p}

        total_eq = cash
        for si, pos in positions.items():
            p = get_price(all_stocks[si])
            total_eq += pos["shares"] * (p if p > 0 else pos["cost"])
        equity_curve.append(total_eq)

    eq = np.array(equity_curve, dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] > 0, eq[:-1], 1)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(240)) if rets.std() > 0 else 0
    peak = np.maximum.accumulate(eq)
    max_dd = float(((peak - eq) / np.where(peak > 0, peak, 1)).max())
    total_ret = eq[-1] / eq[0] - 1
    ann_ret = total_ret / N_DATES * 240
    calmar = ann_ret / max_dd if max_dd > 0 else 0

    return {
        "total_return": round(total_ret, 4),
        "annual_return": round(ann_ret, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "calmar": round(calmar, 4),
    }


# ── 参数扫描主循环 ────────────────────────────────────────────
top_ns    = PARAM_GRID["top_n"]
reb_days  = PARAM_GRID["rebalance_days"]
hist_wts  = PARAM_GRID["hist_weight"]

total_runs = len(top_ns) * len(reb_days) * len(hist_wts)
print(f"\n开始参数扫描: {total_runs} 种组合 ...")

results = []
t0 = time.time()

for i, (top_n, rebal, hw) in enumerate(product(top_ns, reb_days, hist_wts)):
    # 构建融合信号
    fw = 1.0 - hw
    if hw == 0.0:
        signals = factor_rank
    elif hw == 1.0:
        signals = hist_rank
    else:
        signals = np.where(
            ~np.isnan(factor_rank) & ~np.isnan(hist_rank),
            fw * factor_rank + hw * hist_rank,
            np.where(~np.isnan(hist_rank), hist_rank, factor_rank)
        )

    r = run_backtest(signals, top_n, rebal)
    r.update({"top_n": top_n, "rebalance_days": rebal, "hist_weight": hw,
               "factor_weight": round(fw, 1)})
    results.append(r)

    if (i + 1) % 25 == 0:
        elapsed = time.time() - t0
        print(f"  [{i+1}/{total_runs}] elapsed={elapsed:.0f}s", flush=True)

elapsed = time.time() - t0
print(f"\n扫描完成，耗时 {elapsed:.0f}s")

# ── 排序输出 Top 20 ───────────────────────────────────────────
results_sorted = sorted(results, key=lambda x: x["sharpe"], reverse=True)

print(f"\n{'='*80}")
print(f"Top 20 参数组合（按 Sharpe 排序）")
print(f"{'top_n':>6} {'rebal':>6} {'hist_w':>7} {'总收益':>8} {'Sharpe':>8} {'MDD':>8} {'Calmar':>8}")
print(f"{'-'*80}")
for r in results_sorted[:20]:
    print(f"{r['top_n']:>6} {r['rebalance_days']:>6} {r['hist_weight']:>7.1f} "
          f"{r['total_return']*100:>7.2f}% {r['sharpe']:>8.3f} "
          f"{r['max_drawdown']*100:>7.2f}% {r['calmar']:>8.3f}")

# 当前参数基线
baseline = next(r for r in results if r["top_n"] == 10 and r["rebalance_days"] == 20 and r["hist_weight"] == 0.0)
print(f"\n当前参数基线 (top_n=10, rebal=20, hist_w=0.0):")
print(f"  Sharpe={baseline['sharpe']:.3f}, MDD={baseline['max_drawdown']*100:.2f}%, Calmar={baseline['calmar']:.3f}")

best = results_sorted[0]
print(f"\n最优参数 (top_n={best['top_n']}, rebal={best['rebalance_days']}, hist_w={best['hist_weight']}):")
print(f"  Sharpe={best['sharpe']:.3f}, MDD={best['max_drawdown']*100:.2f}%, Calmar={best['calmar']:.3f}")

# 保存结果
output = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "period": f"{BACKTEST_START} ~ {BACKTEST_END}",
    "total_combinations": total_runs,
    "elapsed_seconds": round(elapsed, 1),
    "top20_by_sharpe": results_sorted[:20],
    "baseline": baseline,
    "best": best,
    "all_results": results,
}
with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {OUT_PATH}")
