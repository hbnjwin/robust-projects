"""
HIST vs GRU 样本外回测对比 v2 - 向量化批量推理
预先构建全量时序矩阵，一次性推理所有日期，避免逐日循环慢
"""

import sys, os, json, time
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 配置 ──────────────────────────────────────────────────────────────
BACKTEST_START = "2024-07-01"
BACKTEST_END = "2026-03-13"
INITIAL_CAP = 1_000_000.0
TOP_N = 30
COST_RATE = 0.002
REBAL_DAYS = 5
SEQ_LEN = 20
D_FEAT_GRU = None  # 从 ckpt 读
D_FEAT_HIST = 75
HIDDEN = 128
OUT_PATH = _ROOT / "data/backtest_compare/hist_vs_gru_oos.json"
os.makedirs(OUT_PATH.parent, exist_ok=True)

# ── 1. 加载因子数据 ───────────────────────────────────────────────────
print("加载因子数据 ...", flush=True)
df_all = pd.read_parquet(
    str(_ROOT / "data/factors_full.parquet"),
    filters=[
        ("trade_date", ">=", date(2024, 3, 1)),  # 多3个月预热
        ("trade_date", "<=", date(2026, 3, 13)),
    ],
)
df_all["trade_date"] = pd.to_datetime(df_all["trade_date"])
df_all = df_all.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

SKIP = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d"}
feat_cols = [c for c in df_all.columns if c not in SKIP]
print(f"  {len(df_all)} rows, {df_all['ts_code'].nunique()} stocks", flush=True)

# ── 2. 加载价格数据 ───────────────────────────────────────────────────
print("加载价格数据 ...", flush=True)
try:
    price_df = pd.read_parquet(
        str(_ROOT / "data/daily_price_full.parquet"),
        filters=[("trade_date", ">=", date(2024, 7, 1)), ("trade_date", "<=", date(2026, 3, 13))],
        columns=["ts_code", "trade_date", "close"],
    )
    price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
    # pivot: date × stock
    price_pivot = price_df.pivot(index="trade_date", columns="ts_code", values="close")
    print(f"  价格: {price_pivot.shape}", flush=True)
except Exception as e:
    print(f"  [WARN] 价格加载失败: {e}", flush=True)
    price_pivot = None

# ── 3. 加载 stock2concept ─────────────────────────────────────────────
s2c_matrix = np.load("/vol1/qlib_data/stock2concept/stock2concept.npy")
stock_index = np.load("/vol1/qlib_data/stock2concept/stock_index.npy", allow_pickle=True).item()
N_CONCEPTS = s2c_matrix.shape[1]
UNKNOWN_IDX = s2c_matrix.shape[0] - 1
s2c_tensor = torch.from_numpy(s2c_matrix).float()


def ts2qlib(ts_code):
    code, mkt = ts_code.split(".")
    return mkt + code


# ── 4. 加载模型 ───────────────────────────────────────────────────────
ckpt = torch.load(str(_ROOT / "ml/model_store/v1/gru_model.pt"), map_location="cpu")
D_FEAT_GRU = ckpt["n_features"]
gru_feat_cols = [c for c in ckpt["feature_names"] if c in df_all.columns]


class _GRU(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(
            D_FEAT_GRU,
            ckpt["hidden_size"],
            ckpt["num_layers"],
            batch_first=True,
            dropout=ckpt["dropout"] if ckpt["num_layers"] > 1 else 0,
        )
        self.fc = nn.Sequential(
            nn.Linear(ckpt["hidden_size"], 32), nn.ReLU(), nn.Dropout(ckpt["dropout"]), nn.Linear(32, 1)
        )

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


class _HIST(nn.Module):
    def __init__(self):
        super().__init__()
        self.rnn = nn.GRU(D_FEAT_HIST, HIDDEN, 2, batch_first=True, dropout=0.1)
        self.concept_fc = nn.Linear(HIDDEN, N_CONCEPTS)
        self.concept_emb = nn.Linear(N_CONCEPTS, HIDDEN)
        self.fc_out = nn.Sequential(nn.Linear(HIDDEN * 2, HIDDEN), nn.ReLU(), nn.Dropout(0.1), nn.Linear(HIDDEN, 1))

    def forward(self, x, cm):
        out, _ = self.rnn(x)
        h = out[:, -1, :]
        a = torch.softmax(self.concept_fc(h), dim=-1) * (cm + 1e-6)
        a = a / (a.sum(-1, keepdim=True) + 1e-8)
        return self.fc_out(torch.cat([h, self.concept_emb(a)], -1)).squeeze(-1)


gru_model = _GRU()
gru_model.load_state_dict(ckpt["model_state"])
gru_model.eval()
hist_model = _HIST()
hist_model.load_state_dict(torch.load(str(_ROOT / "ml/model_store/v1/hist_model.pt"), map_location="cpu"))
hist_model.eval()
print(f"GRU loaded (feat={D_FEAT_GRU}), HIST loaded (feat={D_FEAT_HIST})", flush=True)

# ── 5. 预计算每只股票每个交易日的信号（向量化）────────────────────────
print("预计算信号矩阵 ...", flush=True)
t0 = time.time()

trade_dates = sorted(
    df_all[(df_all["trade_date"] >= BACKTEST_START) & (df_all["trade_date"] <= BACKTEST_END)]["trade_date"].unique()
)

all_stocks = sorted(df_all["ts_code"].unique())
stock2i = {s: i for i, s in enumerate(all_stocks)}

# 为每只股票预先构建时序矩阵 [n_dates, SEQ_LEN, n_feat]
# 用 mmap 避免 OOM
MMAP_DIR = "/vol1/mmap_cache/hist_bt"
os.makedirs(MMAP_DIR, exist_ok=True)

gru_sig_path = os.path.join(MMAP_DIR, "gru_signals.npy")
hist_sig_path = os.path.join(MMAP_DIR, "hist_signals.npy")
dates_path = os.path.join(MMAP_DIR, "bt_dates.npy")

N_DATES = len(trade_dates)
N_STOCKS = len(all_stocks)

if os.path.exists(gru_sig_path) and os.path.exists(hist_sig_path):
    print("  复用已有信号矩阵", flush=True)
    gru_signals = np.load(gru_sig_path)  # [N_DATES, N_STOCKS]
    hist_signals = np.load(hist_sig_path)
else:
    gru_signals = np.full((N_DATES, N_STOCKS), np.nan, dtype=np.float32)
    hist_signals = np.full((N_DATES, N_STOCKS), np.nan, dtype=np.float32)

    # 按股票批量处理
    BATCH = 200
    for bi in range(0, N_STOCKS, BATCH):
        batch_stocks = all_stocks[bi : bi + BATCH]
        t1 = time.time()

        gru_X_list = []  # (date_idx, stock_idx, window)
        hist_X_list = []
        sidx_list = []
        di_list = []
        si_list = []

        for code in batch_stocks:
            si = stock2i[code]
            grp = df_all[df_all["ts_code"] == code].sort_values("trade_date")
            dates_arr = grp["trade_date"].values
            gru_feat = np.nan_to_num(grp[gru_feat_cols].values.astype(np.float32), nan=0.0)
            hist_feat = np.nan_to_num(grp[feat_cols].values.astype(np.float32), nan=0.0)
            gru_feat = np.clip(gru_feat, -3, 3)
            hist_feat = np.clip(hist_feat, -3, 3)

            qc = ts2qlib(code)
            sidx = stock_index.get(qc, UNKNOWN_IDX)

            for di, td in enumerate(trade_dates):
                # 找截止 td 的最近 SEQ_LEN 行
                mask = dates_arr <= td
                n = mask.sum()
                if n < SEQ_LEN:
                    continue
                # 最新日期不能超过 td 太远
                last_date = dates_arr[mask][-1]
                if (td - last_date).days > 7:
                    continue
                gru_X_list.append(gru_feat[mask][-SEQ_LEN:])
                hist_X_list.append(hist_feat[mask][-SEQ_LEN:])
                sidx_list.append(sidx)
                di_list.append(di)
                si_list.append(si)

        if not gru_X_list:
            continue

        # 批量推理
        X_gru = torch.from_numpy(np.stack(gru_X_list))
        X_hist = torch.from_numpy(np.stack(hist_X_list))
        sidx_t = torch.tensor(sidx_list, dtype=torch.long)

        with torch.no_grad():
            INFER_BATCH = 4096
            gru_preds, hist_preds = [], []
            for ii in range(0, len(X_gru), INFER_BATCH):
                gru_preds.append(gru_model(X_gru[ii : ii + INFER_BATCH]).numpy())
                cm = s2c_tensor[sidx_t[ii : ii + INFER_BATCH]]
                hist_preds.append(hist_model(X_hist[ii : ii + INFER_BATCH], cm).numpy())
            gru_preds = np.concatenate(gru_preds)
            hist_preds = np.concatenate(hist_preds)

        for k, (di, si) in enumerate(zip(di_list, si_list)):
            gru_signals[di, si] = gru_preds[k]
            hist_signals[di, si] = hist_preds[k]

        elapsed = time.time() - t1
        print(f"  [{bi + len(batch_stocks)}/{N_STOCKS}] {elapsed:.1f}s, samples={len(gru_X_list)}", flush=True)

    np.save(gru_sig_path, gru_signals)
    np.save(hist_sig_path, hist_signals)
    np.save(dates_path, np.array([str(d.date()) for d in trade_dates]))
    print(f"  信号矩阵计算完成，耗时 {time.time() - t0:.0f}s", flush=True)


# ── 6. 回测引擎 ───────────────────────────────────────────────────────
def run_backtest(signals, label):
    print(f"\n{'=' * 50}", flush=True)
    print(f"回测: {label}", flush=True)

    cash = INITIAL_CAP
    positions = {}  # {stock_idx: {"shares": float, "cost": float}}
    equity_curve = [INITIAL_CAP]
    n_trades = 0

    for di, td in enumerate(trade_dates):
        # 当日信号
        sig = signals[di]  # [N_STOCKS]
        valid = ~np.isnan(sig)

        # 当日价格
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
            code = all_stocks[si]
            p = get_price(code)
            total_eq += pos["shares"] * (p if p > 0 else pos["cost"])

        # 再平衡
        if di % REBAL_DAYS == 0 and valid.sum() > 0:
            top_idxs = set(
                np.argsort(sig[valid])[::-1][:TOP_N][np.argsort(sig[valid])[::-1][:TOP_N] < N_STOCKS].tolist()
            )
            # 用 valid 索引映射回全局索引
            valid_idxs = np.where(valid)[0]
            top_scores = sig[valid_idxs]
            top_local = np.argsort(top_scores)[::-1][:TOP_N]
            top_global = set(valid_idxs[top_local].tolist())

            # 卖出
            for si in list(positions.keys()):
                if si not in top_global:
                    code = all_stocks[si]
                    p = get_price(code)
                    if p > 0:
                        cash += positions[si]["shares"] * p * (1 - COST_RATE)
                        n_trades += 1
                    del positions[si]

            # 买入
            alloc = total_eq / TOP_N
            for si in top_global:
                if si not in positions:
                    code = all_stocks[si]
                    p = get_price(code)
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

        # 重新 mark-to-market
        total_eq = cash
        for si, pos in positions.items():
            code = all_stocks[si]
            p = get_price(code)
            total_eq += pos["shares"] * (p if p > 0 else pos["cost"])

        equity_curve.append(total_eq)

        if (di + 1) % 40 == 0:
            ret = (total_eq / INITIAL_CAP - 1) * 100
            print(f"  [{di + 1}/{N_DATES}] {td.date()} eq={total_eq:,.0f} ret={ret:+.2f}%", flush=True)

    eq = np.array(equity_curve, dtype=float)
    total_ret = eq[-1] / eq[0] - 1
    rets = np.diff(eq) / np.where(eq[:-1] > 0, eq[:-1], 1)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(240)) if rets.std() > 0 else 0
    peak = np.maximum.accumulate(eq)
    max_dd = float(((peak - eq) / np.where(peak > 0, peak, 1)).max())
    ann_ret = total_ret / N_DATES * 240

    result = {
        "model": label,
        "total_return": round(total_ret, 4),
        "ann_return": round(ann_ret, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "calmar": round(ann_ret / max_dd, 4) if max_dd > 0 else 0,
        "win_rate": round(float((rets > 0).mean()), 4),
        "n_trades": n_trades,
        "n_days": N_DATES,
    }
    print(f"  {label}: ret={total_ret * 100:+.2f}% sharpe={sharpe:.3f} dd={max_dd * 100:.2f}%", flush=True)
    return result


# ── 7. 运行 ───────────────────────────────────────────────────────────
r_gru = run_backtest(gru_signals, "GRU_OOS")
r_hist = run_backtest(hist_signals, "HIST_OOS")

# 集成信号
ensemble = np.where(
    ~np.isnan(gru_signals) & ~np.isnan(hist_signals),
    0.4 * gru_signals + 0.6 * hist_signals,
    np.where(~np.isnan(hist_signals), hist_signals, gru_signals),
)
r_ens = run_backtest(ensemble, "Ensemble_GRU0.4_HIST0.6")

# ── 8. 汇总 ───────────────────────────────────────────────────────────
baseline = {
    "model": "GRU_prev_baseline",
    "total_return": 0.0655,
    "ann_return": 0.0999,
    "sharpe": 0.6201,
    "max_drawdown": 0.0998,
    "calmar": 1.0009,
}

print("\n" + "=" * 65, flush=True)
print(f"{'模型':<28} {'总收益':>8} {'年化':>8} {'Sharpe':>8} {'最大回撤':>10} {'Calmar':>8}", flush=True)
print("-" * 65, flush=True)
for r in [r_gru, r_hist, r_ens, baseline]:
    print(
        f"{r['model']:<28} {r['total_return'] * 100:>7.2f}% {r['ann_return'] * 100:>7.2f}% "
        f"{r['sharpe']:>8.3f} {r['max_drawdown'] * 100:>9.2f}% {r['calmar']:>8.3f}",
        flush=True,
    )

output = {
    "generated_at": __import__("datetime").datetime.now().isoformat(),
    "period": f"{BACKTEST_START} ~ {BACKTEST_END}",
    "gru": r_gru,
    "hist": r_hist,
    "ensemble": r_ens,
    "baseline": baseline,
}
with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {OUT_PATH}", flush=True)
