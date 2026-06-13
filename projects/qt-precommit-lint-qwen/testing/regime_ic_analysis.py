"""
Regime 分层统计
分析 Factor / HIST 信号在不同市场状态（BULL/NEUTRAL/CRISIS）下的 IC 表现

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/regime_ic_analysis.py
"""

import sys, json
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

MMAP_DIR = "/vol1/mmap_cache/hist_bt"
HORIZON = 20  # 用 T+20（HIST 最优 horizon）
OUT_PATH = _ROOT / "data/backtest_compare/regime_ic_analysis.json"
OUT_PATH.parent.mkdir(exist_ok=True)

# ── 1. 加载信号矩阵 ───────────────────────────────────────────
print("加载信号矩阵 ...")
bt_dates = np.load(f"{MMAP_DIR}/bt_dates.npy", allow_pickle=True)
hist_mat = np.load(f"{MMAP_DIR}/hist_signals.npy")
factor_mat = np.load(f"{MMAP_DIR}/factor_signals.npy")

df_meta = pd.read_parquet(
    str(_ROOT / "data/factors_full.parquet"), filters=[("trade_date", ">=", date(2024, 3, 1))], columns=["ts_code"]
)
all_stocks = sorted(df_meta["ts_code"].unique())
stock2i = {s: i for i, s in enumerate(all_stocks)}

# ── 2. 加载价格数据 ───────────────────────────────────────────
print("加载价格数据 ...")
price_df = pd.read_parquet(
    str(_ROOT / "data/daily_price_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 3, 1))],
    columns=["ts_code", "trade_date", "close"],
)
price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
price_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close").sort_index()

common_stocks = [s for s in all_stocks if s in price_pivot.columns]
price_pivot = price_pivot[common_stocks]
common_idx = [stock2i[s] for s in common_stocks]
date_index = {str(d.date()): i for i, d in enumerate(price_pivot.index)}
price_arr = price_pivot.values
print(f"  价格: {price_pivot.shape}, 共同股票: {len(common_stocks)}")

# ── 3. 检测每日 Regime ────────────────────────────────────────
print("检测 Regime ...")
from live.regime_detector_v2 import RegimeDetectorV2
from live.data_loader import load_market_data

# 加载沪深300指数数据
index_data = load_market_data("2024-03-01", "2026-03-13", ts_code="000300.SH")
detector = RegimeDetectorV2()
regime_map = {}

for d_str in sorted(index_data.keys()):
    if "000300.SH" in index_data[d_str]:
        idx_close = index_data[d_str]["000300.SH"]["close"]
        idx_vol = index_data[d_str]["000300.SH"]["volume"]
        detector.update(idx_close, idx_vol)
        regime_map[d_str] = detector.detect()
    else:
        regime_map[d_str] = "NEUTRAL"

regime_counts = {}
for r in regime_map.values():
    regime_counts[r] = regime_counts.get(r, 0) + 1
print(f"  Regime 分布: {regime_counts}")


# ── 4. 按 Regime 计算 IC ─────────────────────────────────────
def compute_regime_ic(signal_mat, label):
    regime_ics = {"BULL": [], "NEUTRAL": [], "CRISIS": []}

    for di, d_str in enumerate(bt_dates):
        d_str = str(d_str)
        if d_str not in date_index or d_str not in regime_map:
            continue

        pi = date_index[d_str]
        pi_future = pi + HORIZON
        if pi_future >= len(price_pivot.index):
            continue

        p_now = price_arr[pi]
        p_future = price_arr[pi_future]
        with np.errstate(divide="ignore", invalid="ignore"):
            ret = np.where(p_now > 0, (p_future - p_now) / p_now, np.nan)

        sig_row = signal_mat[di][common_idx]
        valid = ~np.isnan(sig_row) & ~np.isnan(ret)
        if valid.sum() < 50:
            continue

        ic, _ = spearmanr(sig_row[valid], ret[valid])
        if not np.isnan(ic):
            regime = regime_map[d_str]
            if regime in regime_ics:
                regime_ics[regime].append(ic)

    results = {}
    for regime, ics in regime_ics.items():
        if ics:
            arr = np.array(ics)
            results[regime] = {
                "mean_ic": round(float(arr.mean()), 4),
                "std_ic": round(float(arr.std()), 4),
                "ic_ir": round(float(arr.mean() / arr.std()) if arr.std() > 0 else 0, 4),
                "n_days": len(ics),
                "positive_rate": round(float((arr > 0).mean()), 4),
            }
        else:
            results[regime] = {"mean_ic": 0, "std_ic": 0, "ic_ir": 0, "n_days": 0, "positive_rate": 0}

    return results


print(f"\n计算 Factor 信号 Regime IC (T+{HORIZON}) ...")
factor_regime = compute_regime_ic(factor_mat, "Factor")

print(f"计算 HIST 信号 Regime IC (T+{HORIZON}) ...")
hist_regime = compute_regime_ic(hist_mat, "HIST")

# ── 5. 输出结果 ───────────────────────────────────────────────
print(f"\n{'=' * 70}")
print(f"Regime 分层 IC 分析（T+{HORIZON}）")
print(
    f"{'Regime':>10} | {'Factor IC':>10} {'Factor IR':>10} {'F+Rate':>8} | {'HIST IC':>10} {'HIST IR':>10} {'H+Rate':>8}"
)
print(f"{'-' * 70}")
for regime in ["BULL", "NEUTRAL", "CRISIS"]:
    fi = factor_regime[regime]
    hi = hist_regime[regime]
    print(
        f"{regime:>10} | {fi['mean_ic']:>10.4f} {fi['ic_ir']:>10.4f} {fi['positive_rate']:>8.1%} | "
        f"{hi['mean_ic']:>10.4f} {hi['ic_ir']:>10.4f} {hi['positive_rate']:>8.1%}"
    )

# ── 6. 结论 ───────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("结论：")
for regime in ["BULL", "NEUTRAL", "CRISIS"]:
    fi = factor_regime[regime]
    hi = hist_regime[regime]
    better = "HIST" if hi["mean_ic"] > fi["mean_ic"] else "Factor"
    print(f"  {regime}: {better} 更强 (Factor IC={fi['mean_ic']:.4f}, HIST IC={hi['mean_ic']:.4f})")

# ── 7. 保存 ───────────────────────────────────────────────────
output = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "horizon": HORIZON,
    "regime_counts": regime_counts,
    "factor_regime_ic": factor_regime,
    "hist_regime_ic": hist_regime,
}
with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {OUT_PATH}")
