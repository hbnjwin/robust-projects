"""
Phase 5: Factor 信号预计算 + Factor vs HIST vs Fusion 对比
在 hist_backtest_compare.py 的框架上扩展

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/phase5_factor_precompute.py
"""
import sys, os, json, time
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 配置（与 hist_backtest_compare.py 保持一致）──────────────
BACKTEST_START = "2024-07-01"
BACKTEST_END   = "2026-03-13"
INITIAL_CAP    = 1_000_000.0
TOP_N          = 30
COST_RATE      = 0.002
REBAL_DAYS     = 5
MMAP_DIR       = "/vol1/mmap_cache/hist_bt"
FACTOR_CACHE   = "/vol1/mmap_cache/hist_bt/factor_signals.npy"
OUT_PATH       = _ROOT / "data/backtest_compare/phase5_fusion.json"
os.makedirs(OUT_PATH.parent, exist_ok=True)

# ── 1. 加载预计算 HIST/GRU 信号 ──────────────────────────────
print("加载预计算信号矩阵 ...")
bt_dates     = np.load(f"{MMAP_DIR}/bt_dates.npy", allow_pickle=True)
hist_signals = np.load(f"{MMAP_DIR}/hist_signals.npy")
gru_signals  = np.load(f"{MMAP_DIR}/gru_signals.npy")

# ── 2. 加载股票列表（与 hist_backtest_compare.py 一致）────────
print("加载股票列表 ...")
df_meta = pd.read_parquet(str(_ROOT / "data/factors_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 3, 1)),
             ("trade_date", "<=", date(2026, 3, 13))],
    columns=["ts_code", "trade_date"])
df_meta["trade_date"] = pd.to_datetime(df_meta["trade_date"])
all_stocks = sorted(df_meta["ts_code"].unique())
stock2i    = {s: i for i, s in enumerate(all_stocks)}
N_STOCKS   = len(all_stocks)
print(f"  股票数: {N_STOCKS}")

# ── 3. 过滤回测区间的日期 ─────────────────────────────────────
trade_dates = [pd.Timestamp(str(d)) for d in bt_dates
               if BACKTEST_START <= str(d) <= BACKTEST_END]
N_DATES = len(trade_dates)
date_strs = [d.strftime("%Y-%m-%d") for d in trade_dates]
date2di = {str(d): i for i, d in enumerate(bt_dates)}
print(f"  回测交易日: {N_DATES} ({BACKTEST_START} ~ {BACKTEST_END})")

# ── 4. 加载价格数据 ───────────────────────────────────────────
print("加载价格数据 ...")
try:
    price_df = pd.read_parquet(str(_ROOT / "data/daily_price_full.parquet"),
        filters=[("trade_date", ">=", date(2024, 7, 1)),
                 ("trade_date", "<=", date(2026, 3, 13))],
        columns=["ts_code", "trade_date", "close"])
    price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
    price_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close")
    print(f"  价格: {price_pivot.shape}")
except Exception as e:
    print(f"  [WARN] 价格加载失败: {e}")
    price_pivot = None

# ── 5. 预计算 Factor 信号矩阵 ─────────────────────────────────
if os.path.exists(FACTOR_CACHE):
    print(f"复用已有 Factor 信号矩阵: {FACTOR_CACHE}")
    factor_signals_full = np.load(FACTOR_CACHE)
else:
    print("预计算 Factor 信号矩阵 ...")
    from live.inline_factor_generator import InlineFactorGenerator

    factor_gen = InlineFactorGenerator()
    factor_signals_full = np.full((len(bt_dates), N_STOCKS), np.nan, dtype=np.float32)

    t0 = time.time()
    for di, d_str in enumerate(bt_dates):
        d_str = str(d_str)
        if d_str < "2024-03-01":
            continue

        td = pd.Timestamp(d_str)
        if price_pivot is None or td not in price_pivot.index:
            continue

        # 构建当日价格字典
        prices_row = price_pivot.loc[td]
        price_dict = {}
        for code in all_stocks:
            if code in prices_row.index:
                p = prices_row[code]
                if not np.isnan(p) and p > 0:
                    price_dict[code] = {"close": float(p), "volume": 0}

        if not price_dict:
            continue

        factor_gen.update(price_dict)
        scores = factor_gen.compute_scores()

        for code, score in scores.items():
            if code in stock2i:
                factor_signals_full[di, stock2i[code]] = score

        if (di + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"  [{di+1}/{len(bt_dates)}] {d_str} elapsed={elapsed:.0f}s", flush=True)

    np.save(FACTOR_CACHE, factor_signals_full)
    print(f"  Factor 信号矩阵已保存: {FACTOR_CACHE}")

# 截取回测区间
factor_signals = np.array([
    factor_signals_full[date2di[d]] for d in date_strs
])
hist_bt   = np.array([hist_signals[date2di[d]] for d in date_strs])
gru_bt    = np.array([gru_signals[date2di[d]]  for d in date_strs])
print(f"  Factor 信号: {factor_signals.shape}, 有效率: {(~np.isnan(factor_signals)).mean():.1%}")

# ── 6. 回测引擎（复用 hist_backtest_compare.py 的逻辑）────────
def run_backtest(signals, label):
    print(f"\n{'='*50}", flush=True)
    print(f"回测: {label}", flush=True)

    cash = INITIAL_CAP
    positions = {}
    equity_curve = [INITIAL_CAP]
    n_trades = 0

    for di, td in enumerate(trade_dates):
        sig = signals[di]
        valid = ~np.isnan(sig)

        if price_pivot is not None and td in price_pivot.index:
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
        if di % REBAL_DAYS == 0 and valid.sum() > 0:
            valid_idxs  = np.where(valid)[0]
            top_scores  = sig[valid_idxs]
            top_local   = np.argsort(top_scores)[::-1][:TOP_N]
            top_global  = set(valid_idxs[top_local].tolist())

            for si in list(positions.keys()):
                if si not in top_global:
                    p = get_price(all_stocks[si])
                    if p > 0:
                        cash += positions[si]["shares"] * p * (1 - COST_RATE)
                        n_trades += 1
                    del positions[si]

            alloc = total_eq / TOP_N
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
                    n_trades += 1

        total_eq = cash
        for si, pos in positions.items():
            p = get_price(all_stocks[si])
            total_eq += pos["shares"] * (p if p > 0 else pos["cost"])

        equity_curve.append(total_eq)

        if (di + 1) % 40 == 0:
            ret = (total_eq / INITIAL_CAP - 1) * 100
            print(f"  [{di+1}/{N_DATES}] {td.date()} eq={total_eq:,.0f} ret={ret:+.2f}%", flush=True)

    eq = np.array(equity_curve, dtype=float)
    rets = np.diff(eq) / np.where(eq[:-1] > 0, eq[:-1], 1)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(240)) if rets.std() > 0 else 0
    peak = np.maximum.accumulate(eq)
    max_dd = float(((peak - eq) / np.where(peak > 0, peak, 1)).max())
    total_ret = eq[-1] / eq[0] - 1
    ann_ret = total_ret / N_DATES * 240

    r = {"model": label, "total_return": round(total_ret, 4),
         "ann_return": round(ann_ret, 4), "sharpe": round(sharpe, 4),
         "max_drawdown": round(max_dd, 4),
         "calmar": round(ann_ret / max_dd, 4) if max_dd > 0 else 0,
         "n_trades": n_trades}
    print(f"  {label}: ret={total_ret*100:+.2f}% sharpe={sharpe:.3f} dd={max_dd*100:.2f}%", flush=True)
    return r

# ── 7. 构建融合信号（Rank 标准化后加权）─────────────────────
def rank_normalize(signals):
    """截面 Rank 标准化 [0,1]"""
    result = np.full_like(signals, np.nan)
    for di in range(signals.shape[0]):
        row = signals[di]
        valid = ~np.isnan(row)
        if valid.sum() < 2:
            continue
        ranks = np.argsort(np.argsort(row[valid]))
        result[di, np.where(valid)[0]] = ranks / (valid.sum() - 1)
    return result

print("\n构建融合信号 ...")
factor_rank = rank_normalize(factor_signals)
hist_rank   = rank_normalize(hist_bt)

# Factor(0.4) + HIST(0.6) Rank 融合
fusion_04_06 = np.where(
    ~np.isnan(factor_rank) & ~np.isnan(hist_rank),
    0.4 * factor_rank + 0.6 * hist_rank,
    np.where(~np.isnan(hist_rank), hist_rank, factor_rank)
)

# Factor(0.5) + HIST(0.5) 等权融合
fusion_05_05 = np.where(
    ~np.isnan(factor_rank) & ~np.isnan(hist_rank),
    0.5 * factor_rank + 0.5 * hist_rank,
    np.where(~np.isnan(hist_rank), hist_rank, factor_rank)
)

# ── 8. 运行所有对比 ───────────────────────────────────────────
r_factor     = run_backtest(factor_signals, "Factor_only")
r_hist       = run_backtest(hist_bt,        "HIST_only")
r_f04_h06    = run_backtest(fusion_04_06,   "Factor0.4_HIST0.6_rank")
r_f05_h05    = run_backtest(fusion_05_05,   "Factor0.5_HIST0.5_rank")

# ── 9. 汇总输出 ───────────────────────────────────────────────
print(f"\n{'='*70}", flush=True)
print(f"{'模型':<32} {'总收益':>8} {'年化':>8} {'Sharpe':>8} {'最大回撤':>10} {'Calmar':>8}", flush=True)
print(f"{'-'*70}", flush=True)
for r in [r_factor, r_hist, r_f04_h06, r_f05_h05]:
    print(f"{r['model']:<32} {r['total_return']*100:>7.2f}% "
          f"{r['ann_return']*100:>7.2f}% {r['sharpe']:>8.3f} "
          f"{r['max_drawdown']*100:>9.2f}% {r['calmar']:>8.3f}", flush=True)

result = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "period": f"{BACKTEST_START} ~ {BACKTEST_END}",
    "factor_only":          r_factor,
    "hist_only":            r_hist,
    "fusion_factor04_hist06": r_f04_h06,
    "fusion_factor05_hist05": r_f05_h05,
}
with open(OUT_PATH, "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {OUT_PATH}", flush=True)
