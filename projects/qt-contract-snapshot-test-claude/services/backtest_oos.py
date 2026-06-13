"""
services/backtest_oos.py — 样本外回测（Out-of-Sample）

用 GRU 模型（训练截止 2024-06）对 2025-07 ~ 2026-03 做纯样本外回测。
同时跑 Qlib-style 和 Replay V5，公平对比。
"""
from __future__ import annotations

import json
import os
import sys
import time
import gc
from datetime import date as _date
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.replay_engine_v5 import ReplayEngineV5
from live.data_loader_fast import load_market_data_fast
from services.backtest_compare import QlibStyleBacktest

GRU_MODEL_PATH = "ml/model_store/v1/gru_model.pt"
FACTORS_FULL = "data/factors_full.parquet"
OUTPUT_DIR = "data/backtest_compare"


class _GRUModel(torch.nn.Module):
    def __init__(self, n_features, hidden_size=64, num_layers=2, dropout=0.1):
        super().__init__()
        self.gru = torch.nn.GRU(
            input_size=n_features, hidden_size=hidden_size,
            num_layers=num_layers, batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 32),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(32, 1),
        )

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


def generate_gru_signals(start: str, end: str) -> dict[str, dict[str, float]]:
    """用 GRU 模型批量生成样本外信号（优化版：按股票预构建窗口）"""
    ckpt = torch.load(GRU_MODEL_PATH, map_location="cpu")
    seq_len = ckpt["seq_len"]
    feature_names = ckpt["feature_names"]
    n_features = ckpt["n_features"]

    model = _GRUModel(n_features, ckpt["hidden_size"], ckpt["num_layers"], ckpt["dropout"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    print(f"[OOS] GRU 模型: valid_IC={ckpt['valid_ic']:.4f} test_IC={ckpt['test_ic']:.4f} seq_len={seq_len}")

    # 按年加载因子数据（需要回测期前 seq_len 天的历史）
    start_year = int(start[:4]) - 1  # 多加载一年确保有足够历史
    end_year = int(end[:4])

    all_df = []
    for year in range(start_year, end_year + 1):
        filters = [
            ("trade_date", ">=", _date(year, 1, 1)),
            ("trade_date", "<=", _date(year, 12, 31)),
        ]
        try:
            df = pd.read_parquet(FACTORS_FULL, filters=filters)
        except Exception:
            df = pd.read_parquet(FACTORS_FULL)
            df = df[pd.to_datetime(df["trade_date"]).dt.year == year]
        if not df.empty:
            all_df.append(df)
            print(f"[OOS] {year}: {len(df)} 行")
        del df; gc.collect()

    df = pd.concat(all_df, ignore_index=True)
    del all_df; gc.collect()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["ts_code", "trade_date"])

    feat_cols = [c for c in feature_names if c in df.columns]
    print(f"[OOS] 总数据: {len(df)} 行, {df['ts_code'].nunique()} 只股票")

    # 预构建：按股票生成所有窗口和对应日期
    print("[OOS] 预构建滑动窗口...", flush=True)
    all_windows = []  # (date_str, ts_code, window_array)
    start_ts = pd.Timestamp(start)

    for ts_code, grp in df.groupby("ts_code"):
        grp = grp.sort_values("trade_date")
        dates = grp["trade_date"].values
        feats = grp[feat_cols].values.astype(np.float32)

        for i in range(seq_len, len(feats)):
            dt = dates[i]
            if dt < start_ts:
                continue
            date_str = str(dt)[:10]
            if date_str > end:
                break
            window = feats[i - seq_len:i]
            window = np.clip(np.nan_to_num(window, nan=0.0, posinf=3.0, neginf=-3.0), -3, 3)
            all_windows.append((date_str, ts_code, window))

    print(f"[OOS] 窗口总数: {len(all_windows):,}", flush=True)
    del df; gc.collect()

    # 按日期分组批量推理
    from collections import defaultdict
    by_date = defaultdict(list)
    for date_str, ts_code, window in all_windows:
        by_date[date_str].append((ts_code, window))
    del all_windows; gc.collect()

    signals = {}
    sorted_dates = sorted(by_date.keys())
    batch_size = 2048

    for i, date_str in enumerate(sorted_dates):
        items = by_date[date_str]
        codes = [c for c, _ in items]
        X = np.stack([w for _, w in items], axis=0)

        preds_list = []
        with torch.no_grad():
            for j in range(0, len(X), batch_size):
                batch = torch.from_numpy(X[j:j + batch_size])
                preds_list.append(model(batch).numpy())

        preds = np.concatenate(preds_list)
        signals[date_str] = {code: float(pred) for code, pred in zip(codes, preds)}

        if (i + 1) % 20 == 0:
            print(f"[OOS] {i+1}/{len(sorted_dates)} 天, {date_str}, {len(codes)} 只股票", flush=True)

    print(f"[OOS] 生成 {len(signals)} 天信号")
    return signals


def run_oos(
    start: str = "2025-07-01",
    end: str = "2026-03-13",
    top_k: int = 30,
    rebalance_days: int = 5,
):
    print(f"[OOS backtest] {start} ~ {end}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 生成纯 GRU 样本外信号
    t0 = time.time()
    signals = generate_gru_signals(start, end)
    print(f"  信号生成: {time.time()-t0:.1f}s")

    # 2. 加载行情
    t1 = time.time()
    market_data = load_market_data_fast(start, end)
    print(f"  行情: {len(market_data)} 天 ({time.time()-t1:.1f}s)")

    # 3. Qlib-style 回测（纯 GRU 信号）
    print("\n── Qlib-style (GRU OOS) ──")
    t2 = time.time()
    qlib_bt = QlibStyleBacktest(
        scores=signals,
        prices=market_data,
        top_k=top_k,
        rebalance_days=rebalance_days,
    )
    qlib_result = qlib_bt.run()
    print(f"  耗时: {time.time()-t2:.1f}s")
    print(f"  指标: {json.dumps(qlib_result['metrics'], indent=2)}")

    # 4. Replay V5 回测（纯 Factor 模式，GRU 信号）
    print("\n── Replay V5 (GRU OOS, 纯 Factor) ──")
    t3 = time.time()
    v5_engine = ReplayEngineV5(
        market_data=market_data,
        start_date=start,
        end_date=end,
        ml_signals=signals,
        trend_ratio=0.0,
        lowvol_ratio=0.0,
        factor_ratio=1.0,
        cash_ratio=0.0,
        factor_top_n=top_k,
        factor_rebalance_days=rebalance_days,
    )
    v5_curve = v5_engine.run()
    print(f"  耗时: {time.time()-t3:.1f}s")

    # V5 指标
    v5_eq = [c["equity"] for c in v5_curve]
    v5_ret = [(v5_eq[i] - v5_eq[i-1]) / v5_eq[i-1] for i in range(1, len(v5_eq))]
    v5_r = np.array(v5_ret)
    n = len(v5_r)
    v5_total = v5_eq[-1] / v5_eq[0] - 1 if v5_eq else 0
    v5_ann = (1 + v5_total) ** (252 / n) - 1 if n > 0 else 0
    v5_vol = v5_r.std() * np.sqrt(252) if n > 0 else 0
    v5_sharpe = (v5_ann - 0.02) / v5_vol if v5_vol > 0 else 0
    peak = v5_eq[0]
    v5_maxdd = 0
    for eq in v5_eq:
        peak = max(peak, eq)
        v5_maxdd = max(v5_maxdd, (peak - eq) / peak)

    v5_metrics = {
        "total_return": round(v5_total, 4),
        "ann_return": round(v5_ann, 4),
        "ann_vol": round(v5_vol, 4),
        "sharpe": round(v5_sharpe, 4),
        "max_drawdown": round(v5_maxdd, 4),
        "calmar": round(v5_ann / v5_maxdd, 4) if v5_maxdd > 0 else 0,
        "win_rate": round((v5_r > 0).sum() / n, 4) if n > 0 else 0,
        "n_days": n,
    }
    print(f"  指标: {json.dumps(v5_metrics, indent=2)}")

    # 5. 对比
    print("\n── 对比 (GRU 样本外) ──")
    comparison = {
        "period": f"{start} ~ {end}",
        "model": "GRU_OOS (train<=2024-06)",
        "qlib_style_gru": qlib_result["metrics"],
        "replay_v5_gru": v5_metrics,
        "diff": {},
    }
    for key in ["total_return", "ann_return", "sharpe", "max_drawdown", "calmar"]:
        q = qlib_result["metrics"].get(key, 0)
        v = v5_metrics.get(key, 0)
        comparison["diff"][key] = round(q - v, 4)
        print(f"  {key:15s}  qlib={q:+.4f}  v5={v:+.4f}  diff={q-v:+.4f}")

    out_path = os.path.join(OUTPUT_DIR, f"oos_{start}_{end}.json")
    with open(out_path, "w") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    print(f"\n  保存: {out_path}")
    return comparison


if __name__ == "__main__":
    run_oos()
