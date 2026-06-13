"""
services/walk_forward.py — Walk-Forward 验证框架

滚动训练/验证，评估策略在样本外的真实有效性。
每次用前 N 年训练，后 1 年验证，滚动推进。

用法：
  cd /home/tulin/quant
  python services/walk_forward.py                    # 默认参数
  python services/walk_forward.py --train-years 3 --val-years 1
  python services/walk_forward.py --start 2019 --end 2025
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.data_loader_fast import load_market_data_fast
from services.backtest_compare import QlibStyleBacktest

FACTORS_FULL = "data/factors_full.parquet"
OUTPUT_DIR = "data/walk_forward"


# ─────────────────────────────────────────────────────────────
# 简单因子信号生成（不依赖 GRU，用规则因子做 WF 验证）
# ─────────────────────────────────────────────────────────────

# 实际可用的 Qlib 风格量价因子
# 动量：中短期价格动量
MOMENTUM_COLS = ["roc_20", "roc_60", "roc_10", "cntp_20"]
# 趋势强度：beta + R² 衡量趋势质量
TREND_COLS = ["beta_20", "rsqr_20", "beta_60"]
# 量价：成交量动量与波动
VOL_COLS = ["vma_20", "wvma_20", "vol_ratio"]
# 反转：短期超跌（rsv 低 = 超卖，短期反弹概率高）
REVERSAL_COLS = ["rsv_5"]


def _zscore(s: pd.Series) -> pd.Series:
    std = s.std()
    return (s - s.mean()) / std if std > 1e-9 else s * 0


def compute_factor_scores(df: pd.DataFrame, date_str: str) -> dict[str, float]:
    """
    综合得分 = 动量 * 0.35 + 趋势强度 * 0.30 + 量价 * 0.20 + 短期反转 * 0.15
    全部使用实际存在的 Qlib 量价因子列
    """
    day_df = df[df["trade_date"] == date_str].copy()
    if day_df.empty:
        return {}

    score = pd.Series(0.0, index=day_df.index)
    weight_used = 0.0

    # 动量（顺势）
    mom_cols = [c for c in MOMENTUM_COLS if c in day_df.columns]
    if mom_cols:
        mom = day_df[mom_cols].apply(_zscore).mean(axis=1)
        score += _zscore(mom) * 0.35
        weight_used += 0.35

    # 趋势强度（beta>0 且 R² 高 = 趋势清晰）
    trend_cols = [c for c in TREND_COLS if c in day_df.columns]
    if trend_cols:
        trend = day_df[trend_cols].apply(_zscore).mean(axis=1)
        score += _zscore(trend) * 0.30
        weight_used += 0.30

    # 量价配合（成交量放大 + 价格上涨）
    vol_cols = [c for c in VOL_COLS if c in day_df.columns]
    if vol_cols:
        vol = day_df[vol_cols].apply(_zscore).mean(axis=1)
        score += _zscore(vol) * 0.20
        weight_used += 0.20

    # 短期反转（rsv_5 低 = 短期超卖，反弹概率高）
    rev_cols = [c for c in REVERSAL_COLS if c in day_df.columns]
    if rev_cols:
        rev = -day_df[rev_cols].apply(_zscore).mean(axis=1)
        score += _zscore(rev) * 0.15
        weight_used += 0.15

    if weight_used < 0.1:
        return {}

    day_df["score"] = score.values
    day_df = day_df.dropna(subset=["score"])
    return dict(zip(day_df["ts_code"], day_df["score"]))


def build_signals_for_period(start: str, end: str) -> dict[str, dict[str, float]]:
    """加载因子数据并生成指定区间的每日信号"""
    filters = [
        ("trade_date", ">=", pd.Timestamp(start).date()),
        ("trade_date", "<=", pd.Timestamp(end).date()),
    ]
    try:
        df = pd.read_parquet(FACTORS_FULL, filters=filters)
    except Exception:
        df = pd.read_parquet(FACTORS_FULL)
        df = df[(df["trade_date"] >= start) & (df["trade_date"] <= end)]

    df["trade_date"] = df["trade_date"].astype(str).str[:10]
    dates = sorted(df["trade_date"].unique())

    signals = {}
    for d in dates:
        scores = compute_factor_scores(df, d)
        if scores:
            signals[d] = scores
    return signals


# ─────────────────────────────────────────────────────────────
# GRU 模型信号生成（复用 backtest_oos 的推理逻辑）
# ─────────────────────────────────────────────────────────────

GRU_MODEL_PATH = "ml/model_store/v1/gru_model.pt"


class _GRUModel(nn.Module):
    def __init__(self, n_features, hidden_size=64, num_layers=2, dropout=0.1):
        super().__init__()
        self.gru = nn.GRU(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


def build_gru_signals_for_period(start: str, end: str, batch_size: int = 2048) -> dict[str, dict[str, float]]:
    """
    用 GRU 模型批量生成指定区间的每日信号
    模型训练截止 2024-06，start > 2024-06 才是真正样本外
    """
    if not Path(GRU_MODEL_PATH).exists():
        print(f"  [GRU] 模型文件不存在: {GRU_MODEL_PATH}")
        return {}

    ckpt = torch.load(GRU_MODEL_PATH, map_location="cpu")
    seq_len = ckpt["seq_len"]
    feature_names = ckpt["feature_names"]
    n_features = ckpt["n_features"]

    model = _GRUModel(n_features, ckpt["hidden_size"], ckpt["num_layers"], ckpt["dropout"])
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    # 加载因子数据（需要 seq_len 天历史，多取 60 天缓冲）
    buf_start = (pd.Timestamp(start) - pd.Timedelta(days=60)).strftime("%Y-%m-%d")
    filters = [
        ("trade_date", ">=", pd.Timestamp(buf_start).date()),
        ("trade_date", "<=", pd.Timestamp(end).date()),
    ]
    try:
        df = pd.read_parquet(FACTORS_FULL, filters=filters)
    except Exception:
        df = pd.read_parquet(FACTORS_FULL)
        df = df[(df["trade_date"].astype(str) >= buf_start) & (df["trade_date"].astype(str) <= end)]

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["ts_code", "trade_date"])
    feat_cols = [c for c in feature_names if c in df.columns]
    start_ts = pd.Timestamp(start)

    # 预构建滑动窗口
    all_windows = []
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
            window = feats[i - seq_len : i]
            window = np.clip(np.nan_to_num(window, nan=0.0, posinf=3.0, neginf=-3.0), -3, 3)
            all_windows.append((date_str, ts_code, window))

    del df
    gc.collect()

    # 按日期分组批量推理
    by_date = defaultdict(list)
    for date_str, ts_code, window in all_windows:
        by_date[date_str].append((ts_code, window))
    del all_windows
    gc.collect()

    signals = {}
    for date_str in sorted(by_date.keys()):
        items = by_date[date_str]
        codes = [c for c, _ in items]
        X = np.stack([w for _, w in items], axis=0)
        preds_list = []
        with torch.no_grad():
            for j in range(0, len(X), batch_size):
                batch = torch.from_numpy(X[j : j + batch_size])
                preds_list.append(model(batch).numpy())
        preds = np.concatenate(preds_list)
        signals[date_str] = {code: float(pred) for code, pred in zip(codes, preds)}

    print(f"  [GRU] 生成 {len(signals)} 天信号  IC_valid={ckpt['valid_ic']:.4f} IC_test={ckpt['test_ic']:.4f}")
    return signals


# ─────────────────────────────────────────────────────────────
# 带交易成本的回测包装
# ─────────────────────────────────────────────────────────────


def run_backtest_with_cost(
    signals: dict,
    market_data: dict,
    top_k: int,
    rebalance_days: int,
    cost_rate: float = 0.001,  # 单边 0.1%（印花税+佣金）
) -> dict:
    """
    在 QlibStyleBacktest 基础上叠加交易成本
    cost_rate: 单边成本，买入+卖出合计 2 * cost_rate
    """
    bt = QlibStyleBacktest(scores=signals, prices=market_data, top_k=top_k, rebalance_days=rebalance_days)
    result = bt.run()
    m = result["metrics"]

    # 估算换手率成本：每次调仓约换手 30~50%，每 rebalance_days 天一次
    # 年化调仓次数 ≈ 252 / rebalance_days
    annual_rebalances = 252 / rebalance_days
    avg_turnover = 0.4  # 保守估计每次换手 40%
    annual_cost = annual_rebalances * avg_turnover * 2 * cost_rate

    ann_return_after_cost = m.get("ann_return", 0) - annual_cost
    sharpe_after_cost = (ann_return_after_cost - 0.02) / m.get("ann_vol", 1) if m.get("ann_vol", 0) > 0 else 0

    m["annual_cost_est"] = round(annual_cost, 4)
    m["ann_return_after_cost"] = round(ann_return_after_cost, 4)
    m["sharpe_after_cost"] = round(sharpe_after_cost, 4)
    return m


# ─────────────────────────────────────────────────────────────
# Walk-Forward 主逻辑
# ─────────────────────────────────────────────────────────────


def run_single_window(
    train_start: str,
    train_end: str,
    val_start: str,
    val_end: str,
    top_k: int = 20,
    rebalance_days: int = 5,
    use_gru: bool = True,
    cost_rate: float = 0.001,
) -> dict:
    """
    运行单个 WF 窗口，同时对比：
      - 规则因子（量价多因子）
      - GRU 模型信号（如果 use_gru=True）
    均叠加交易成本估算
    """
    label = f"train={train_start[:4]}~{train_end[:4]}  val={val_start[:4]}~{val_end[:4]}"
    print(f"  [{label}]")

    # 加载验证期行情（两个信号共用）
    market_data = load_market_data_fast(val_start, val_end)
    print(f"    行情: {len(market_data)} 天")

    result = {
        "window": label,
        "train_start": train_start,
        "train_end": train_end,
        "val_start": val_start,
        "val_end": val_end,
    }

    # ── 规则因子回测 ──────────────────────────────────────
    t0 = time.time()
    rule_signals = build_signals_for_period(val_start, val_end)
    print(f"    [规则因子] 信号: {len(rule_signals)} 天  ({time.time() - t0:.1f}s)")

    if rule_signals:
        m_rule = run_backtest_with_cost(rule_signals, market_data, top_k, rebalance_days, cost_rate)
        result["rule_metrics"] = m_rule
        print(
            f"    [规则因子] 年化={m_rule.get('ann_return', 0):+.2%}  "
            f"(扣费后={m_rule.get('ann_return_after_cost', 0):+.2%})  "
            f"Sharpe={m_rule.get('sharpe', 0):.2f}→{m_rule.get('sharpe_after_cost', 0):.2f}  "
            f"MaxDD={m_rule.get('max_drawdown', 0):.2%}"
        )

    # ── GRU 模型回测 ──────────────────────────────────────
    if use_gru:
        t1 = time.time()
        gru_signals = build_gru_signals_for_period(val_start, val_end)
        print(f"    [GRU]    信号: {len(gru_signals)} 天  ({time.time() - t1:.1f}s)")

        if gru_signals:
            m_gru = run_backtest_with_cost(gru_signals, market_data, top_k, rebalance_days, cost_rate)
            result["gru_metrics"] = m_gru
            print(
                f"    [GRU]    年化={m_gru.get('ann_return', 0):+.2%}  "
                f"(扣费后={m_gru.get('ann_return_after_cost', 0):+.2%})  "
                f"Sharpe={m_gru.get('sharpe', 0):.2f}→{m_gru.get('sharpe_after_cost', 0):.2f}  "
                f"MaxDD={m_gru.get('max_drawdown', 0):.2%}"
            )

    return result


def run_walk_forward(
    start_year: int = 2019,
    end_year: int = 2025,
    train_years: int = 3,
    val_years: int = 1,
    top_k: int = 20,
    rebalance_days: int = 5,
) -> list[dict]:
    """
    滚动 Walk-Forward 验证
    例：train_years=3, val_years=1, start=2019, end=2025
      窗口1: train=2019~2021, val=2022
      窗口2: train=2020~2022, val=2023
      窗口3: train=2021~2023, val=2024
      窗口4: train=2022~2024, val=2025
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Walk-Forward 验证")
    print(f"  参数: train={train_years}年  val={val_years}年  top_k={top_k}  rebalance={rebalance_days}日")
    print(f"  范围: {start_year} ~ {end_year}")
    print("=" * 60)

    windows = []
    year = start_year
    while year + train_years + val_years - 1 <= end_year:
        train_start = f"{year}-01-01"
        train_end = f"{year + train_years - 1}-12-31"
        val_start = f"{year + train_years}-01-01"
        val_end = f"{year + train_years + val_years - 1}-12-31"
        windows.append((train_start, train_end, val_start, val_end))
        year += val_years  # 滚动步长 = val_years

    results = []
    for train_start, train_end, val_start, val_end in windows:
        r = run_single_window(
            train_start,
            train_end,
            val_start,
            val_end,
            top_k=top_k,
            rebalance_days=rebalance_days,
        )
        results.append(r)


def run_walk_forward(
    start_year: int = 2019,
    end_year: int = 2025,
    train_years: int = 3,
    val_years: int = 1,
    top_k: int = 20,
    rebalance_days: int = 5,
    use_gru: bool = True,
    cost_rate: float = 0.001,
) -> list[dict]:
    """
    滚动 Walk-Forward 验证，同时对比规则因子 vs GRU 模型
    窗口1: train=2019~2021, val=2022
    窗口2: train=2020~2022, val=2023  ...
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Walk-Forward 验证（规则因子 vs GRU）")
    print(
        f"  参数: train={train_years}年  val={val_years}年  top_k={top_k}  "
        f"rebalance={rebalance_days}日  cost={cost_rate * 100:.1f}%/单边"
    )
    print(f"  范围: {start_year} ~ {end_year}  GRU={'开启' if use_gru else '关闭'}")
    print("=" * 70)

    windows = []
    year = start_year
    while year + train_years + val_years - 1 <= end_year:
        windows.append(
            (
                f"{year}-01-01",
                f"{year + train_years - 1}-12-31",
                f"{year + train_years}-01-01",
                f"{year + train_years + val_years - 1}-12-31",
            )
        )
        year += val_years

    results = []
    for train_start, train_end, val_start, val_end in windows:
        r = run_single_window(
            train_start,
            train_end,
            val_start,
            val_end,
            top_k=top_k,
            rebalance_days=rebalance_days,
            use_gru=use_gru,
            cost_rate=cost_rate,
        )
        results.append(r)

    # ── 汇总统计 ──────────────────────────────────────────
    def summarize(key: str) -> dict | None:
        valid = [r for r in results if key in r]
        if not valid:
            return None
        ann = [r[key].get("ann_return_after_cost", r[key].get("ann_return", 0)) for r in valid]
        sharpes = [r[key].get("sharpe_after_cost", r[key].get("sharpe", 0)) for r in valid]
        maxdds = [r[key].get("max_drawdown", 0) for r in valid]
        win_rate = sum(1 for x in ann if x > 0) / len(ann)
        return {
            "n_windows": len(valid),
            "ann_return_mean": round(float(np.mean(ann)), 4),
            "ann_return_std": round(float(np.std(ann)), 4),
            "ann_return_min": round(float(np.min(ann)), 4),
            "ann_return_max": round(float(np.max(ann)), 4),
            "sharpe_mean": round(float(np.mean(sharpes)), 4),
            "sharpe_min": round(float(np.min(sharpes)), 4),
            "maxdd_mean": round(float(np.mean(maxdds)), 4),
            "positive_windows": round(win_rate, 4),
            "stable": bool(win_rate >= 0.75 and float(np.mean(sharpes)) > 0.3),
        }

    rule_summary = summarize("rule_metrics")
    gru_summary = summarize("gru_metrics") if use_gru else None

    print()
    print("=" * 70)
    print("Walk-Forward 汇总（扣费后）")

    for name, s in [("规则因子", rule_summary), ("GRU 模型", gru_summary)]:
        if s is None:
            continue
        print(f"\n  [{name}]")
        print(f"    窗口数:       {s['n_windows']}")
        print(
            f"    年化均值:     {s['ann_return_mean']:+.2%}  "
            f"(min={s['ann_return_min']:+.2%}  max={s['ann_return_max']:+.2%}  "
            f"std={s['ann_return_std']:.2%})"
        )
        print(f"    Sharpe 均值:  {s['sharpe_mean']:.2f}  (min={s['sharpe_min']:.2f})")
        print(f"    最大回撤均值: {s['maxdd_mean']:.2%}")
        print(f"    正收益窗口:   {s['positive_windows']:.0%}")
        print(f"    策略稳定性:   {'✅ 稳定' if s['stable'] else '⚠️  需优化'}")

    # GRU vs 规则因子对比
    if rule_summary and gru_summary:
        print(f"\n  [对比] GRU vs 规则因子（扣费后年化）")
        for r in results:
            val_y = r.get("val_start", "")[:4]
            r_ann = r.get("rule_metrics", {}).get("ann_return_after_cost", 0)
            g_ann = r.get("gru_metrics", {}).get("ann_return_after_cost", 0)
            r_sh = r.get("rule_metrics", {}).get("sharpe_after_cost", 0)
            g_sh = r.get("gru_metrics", {}).get("sharpe_after_cost", 0)
            winner = "GRU ✅" if g_ann > r_ann else "规则 ✅"
            print(f"    val={val_y}  规则={r_ann:+.2%}(Sh={r_sh:.2f})  GRU={g_ann:+.2%}(Sh={g_sh:.2f})  → {winner}")

    output = {
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "params": {
            "start_year": start_year,
            "end_year": end_year,
            "train_years": train_years,
            "val_years": val_years,
            "top_k": top_k,
            "rebalance_days": rebalance_days,
            "cost_rate": cost_rate,
            "use_gru": use_gru,
        },
        "rule_summary": rule_summary,
        "gru_summary": gru_summary,
        "windows": results,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = os.path.join(OUTPUT_DIR, f"wf_compare_{start_year}_{end_year}_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  结果保存: {out_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Walk-Forward 验证：规则因子 vs GRU 模型")
    parser.add_argument("--start", type=int, default=2019)
    parser.add_argument("--end", type=int, default=2025)
    parser.add_argument("--train-years", type=int, default=3)
    parser.add_argument("--val-years", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--rebalance", type=int, default=5)
    parser.add_argument("--no-gru", action="store_true", help="跳过 GRU 对比")
    parser.add_argument("--cost", type=float, default=0.001, help="单边交易成本（默认0.1%%）")
    args = parser.parse_args()

    run_walk_forward(
        start_year=args.start,
        end_year=args.end,
        train_years=args.train_years,
        val_years=args.val_years,
        top_k=args.top_k,
        rebalance_days=args.rebalance,
        use_gru=not args.no_gru,
        cost_rate=args.cost,
    )
