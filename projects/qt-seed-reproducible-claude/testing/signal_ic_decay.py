"""
信号衰减测试（IC Decay Analysis）
测试 Factor / HIST 信号在 T+1/3/5/10/20/30 的 IC（Spearman 相关系数）

IC = corr(signal_t, return_t+n)

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/signal_ic_decay.py
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
HORIZONS = [1, 3, 5, 10, 20, 30]   # T+N 天
OUT_PATH = _ROOT / "data/backtest_compare/ic_decay.json"
OUT_PATH.parent.mkdir(exist_ok=True)

# ── 1. 加载信号矩阵 ───────────────────────────────────────────
print("加载信号矩阵 ...")
bt_dates   = np.load(f"{MMAP_DIR}/bt_dates.npy", allow_pickle=True)
hist_mat   = np.load(f"{MMAP_DIR}/hist_signals.npy")
factor_mat = np.load(f"{MMAP_DIR}/factor_signals.npy")

# 股票列表
df_meta = pd.read_parquet(str(_ROOT / "data/factors_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 3, 1))],
    columns=["ts_code"])
all_stocks = sorted(df_meta["ts_code"].unique())
N_STOCKS   = len(all_stocks)
N_DATES    = len(bt_dates)
print(f"  {N_DATES} 天 × {N_STOCKS} 只股票")

# ── 2. 加载价格数据，计算未来 N 日收益率 ─────────────────────
print("加载价格数据 ...")
price_df = pd.read_parquet(str(_ROOT / "data/daily_price_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 3, 1))],
    columns=["ts_code", "trade_date", "close"])
price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
price_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close")
price_pivot = price_pivot.sort_index()

# 对齐股票列表
common_stocks = [s for s in all_stocks if s in price_pivot.columns]
price_pivot = price_pivot[common_stocks]
stock2i = {s: i for i, s in enumerate(all_stocks)}
common_idx = [stock2i[s] for s in common_stocks]

print(f"  价格数据: {price_pivot.shape}, 共同股票: {len(common_stocks)}")

# 构建日期索引
date_index = {str(d.date()): i for i, d in enumerate(price_pivot.index)}
price_arr  = price_pivot.values  # [N_PRICE_DATES, N_COMMON_STOCKS]

# ── 3. 计算 IC Decay ─────────────────────────────────────────
def compute_ic_decay(signal_mat, label):
    """
    对每个 horizon 计算截面 IC，返回 {horizon: mean_ic, std_ic, ic_ir}
    """
    results = {}
    for horizon in HORIZONS:
        ic_list = []

        for di, d_str in enumerate(bt_dates):
            d_str = str(d_str)
            if d_str not in date_index:
                continue

            pi = date_index[d_str]
            pi_future = pi + horizon

            if pi_future >= len(price_pivot.index):
                continue

            # 未来 N 日收益率
            p_now    = price_arr[pi]
            p_future = price_arr[pi_future]
            with np.errstate(divide='ignore', invalid='ignore'):
                ret = np.where(p_now > 0, (p_future - p_now) / p_now, np.nan)

            # 当日信号（只取共同股票）
            sig_row = signal_mat[di][common_idx]

            # 过滤有效值
            valid = ~np.isnan(sig_row) & ~np.isnan(ret)
            if valid.sum() < 50:
                continue

            ic, _ = spearmanr(sig_row[valid], ret[valid])
            if not np.isnan(ic):
                ic_list.append(ic)

        if ic_list:
            ic_arr = np.array(ic_list)
            mean_ic = float(np.mean(ic_arr))
            std_ic  = float(np.std(ic_arr))
            ic_ir   = mean_ic / std_ic if std_ic > 0 else 0.0
            results[horizon] = {
                "mean_ic": round(mean_ic, 4),
                "std_ic":  round(std_ic, 4),
                "ic_ir":   round(ic_ir, 4),
                "n_days":  len(ic_list),
            }
        else:
            results[horizon] = {"mean_ic": 0, "std_ic": 0, "ic_ir": 0, "n_days": 0}

    return results

print("\n计算 Factor 信号 IC Decay ...")
factor_ic = compute_ic_decay(factor_mat, "Factor")

print("计算 HIST 信号 IC Decay ...")
hist_ic = compute_ic_decay(hist_mat, "HIST")

# ── 4. 输出结果 ───────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"{'Horizon':>8} | {'Factor IC':>10} {'Factor IR':>10} | {'HIST IC':>10} {'HIST IR':>10}")
print(f"{'-'*65}")
for h in HORIZONS:
    fi = factor_ic[h]
    hi = hist_ic[h]
    print(f"  T+{h:<5} | {fi['mean_ic']:>10.4f} {fi['ic_ir']:>10.4f} | "
          f"{hi['mean_ic']:>10.4f} {hi['ic_ir']:>10.4f}")

# ── 5. 分析结论 ───────────────────────────────────────────────
print(f"\n{'='*65}")
print("信号衰减分析：")

# 找 Factor IC 最高的 horizon
best_factor_h = max(HORIZONS, key=lambda h: factor_ic[h]["mean_ic"])
best_hist_h   = max(HORIZONS, key=lambda h: hist_ic[h]["mean_ic"])
print(f"  Factor 信号最强 horizon: T+{best_factor_h} (IC={factor_ic[best_factor_h]['mean_ic']:.4f})")
print(f"  HIST   信号最强 horizon: T+{best_hist_h}   (IC={hist_ic[best_hist_h]['mean_ic']:.4f})")

# 判断信号是否短期化
t1_ic = factor_ic[1]["mean_ic"]
t30_ic = factor_ic[30]["mean_ic"]
if abs(t1_ic) > abs(t30_ic) * 2:
    print(f"  ⚠️  Factor 信号短期化：T+1 IC={t1_ic:.4f} >> T+30 IC={t30_ic:.4f}")
    print(f"     建议：缩短调仓周期至 5-10 日")
elif abs(t30_ic) >= abs(t1_ic) * 0.7:
    print(f"  ✅ Factor 信号持续性好：T+1 IC={t1_ic:.4f}, T+30 IC={t30_ic:.4f}")
    print(f"     建议：30 日调仓周期合理")
else:
    print(f"  📊 Factor 信号中等衰减：T+1 IC={t1_ic:.4f}, T+30 IC={t30_ic:.4f}")
    print(f"     建议：10-20 日调仓周期")

# ── 6. 保存结果 ───────────────────────────────────────────────
output = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "horizons": HORIZONS,
    "factor_ic_decay": factor_ic,
    "hist_ic_decay":   hist_ic,
    "conclusion": {
        "best_factor_horizon": best_factor_h,
        "best_hist_horizon":   best_hist_h,
        "factor_t1_ic":  factor_ic[1]["mean_ic"],
        "factor_t30_ic": factor_ic[30]["mean_ic"],
    }
}
with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {OUT_PATH}")
