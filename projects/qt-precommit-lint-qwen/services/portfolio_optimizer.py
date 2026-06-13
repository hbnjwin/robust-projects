"""
services/portfolio_optimizer.py — 组合优化器

输入: ML 集成信号 (score) + 风险因子
输出: 优化后的持仓权重 {ts_code: weight}

优化目标: 最大化预期收益（score加权），约束:
  - 个股权重上限 (max_weight)
  - 最小持仓数 (min_stocks)
  - 波动率惩罚 (risk_aversion)
  - 高 beta 惩罚

方法: 无需 scipy.optimize，用解析法:
  1. 从 top_pool 中筛选候选股
  2. 用 score / risk 计算风险调整后得分
  3. 按调整后得分分配权重（softmax 归一化）
  4. 截断到 max_weight，重新归一化
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FACTORS_PATH = "data/factors_latest.parquet"
SIGNAL_DIR = "data/signals"
OUTPUT_DIR = "data/portfolio"

# 默认参数
DEFAULT_CONFIG = {
    "top_pool": 100,  # 候选池大小
    "max_stocks": 30,  # 最终持仓数
    "min_stocks": 10,  # 最少持仓数
    "max_weight": 0.08,  # 单只上限 8%
    "risk_aversion": 1.0,  # 波动率惩罚系数
    "beta_penalty": 0.5,  # 高 beta 惩罚
    "softmax_temp": 5.0,  # softmax 温度（越高越集中）
}


def load_signals(date: str | None = None) -> dict:
    """加载最新信号文件"""
    if date:
        path = os.path.join(SIGNAL_DIR, f"{date}.json")
    else:
        files = sorted(os.listdir(SIGNAL_DIR))
        if not files:
            raise FileNotFoundError("No signal files found")
        path = os.path.join(SIGNAL_DIR, files[-1])

    with open(path) as f:
        return json.load(f)


def load_risk_factors(date: str | None = None) -> pd.DataFrame:
    """加载风险因子（最新交易日）"""
    df = pd.read_parquet(FACTORS_PATH)
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    if date:
        target = pd.Timestamp(date)
        day_df = df[df["trade_date"] == target]
        if day_df.empty:
            target = df["trade_date"].max()
            day_df = df[df["trade_date"] == target]
    else:
        target = df["trade_date"].max()
        day_df = df[df["trade_date"] == target]

    return day_df.set_index("ts_code")[["std_20", "beta_20", "std_60", "vol_ratio"]]


def optimize(
    signals: dict | None = None,
    date: str | None = None,
    config: dict | None = None,
) -> dict:
    """
    组合优化主函数

    Returns:
        {
            "date": str,
            "regime": str,
            "weights": {ts_code: float},  # 归一化权重，sum=1
            "stats": {...},
        }
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    # 加载信号
    if signals is None:
        signals = load_signals(date)
    sig_date = signals["date"]
    regime = signals.get("regime", "NEUTRAL")
    all_scores = signals.get("all_signals", {})

    if not all_scores:
        print("[optimizer] 无信号数据")
        return {"date": sig_date, "regime": regime, "weights": {}, "stats": {}}

    # 取 top_pool 候选
    ranked = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)
    pool = dict(ranked[: cfg["top_pool"]])

    # 加载风险因子
    try:
        risk_df = load_risk_factors(sig_date)
    except Exception as e:
        print(f"[optimizer] 风险因子加载失败: {e}，使用等权")
        risk_df = pd.DataFrame()

    # 计算风险调整后得分
    adjusted_scores = {}
    for code, score in pool.items():
        risk_penalty = 0.0
        if not risk_df.empty and code in risk_df.index:
            row = risk_df.loc[code]
            std_20 = row.get("std_20", 0) or 0
            beta_20 = row.get("beta_20", 1) or 1

            # 波动率惩罚：std_20 越大，惩罚越重
            risk_penalty += cfg["risk_aversion"] * max(0, std_20)

            # 高 beta 惩罚：beta > 1.5 时惩罚
            if abs(beta_20) > 1.5:
                risk_penalty += cfg["beta_penalty"] * (abs(beta_20) - 1.0)

        adjusted_scores[code] = score - risk_penalty

    # 按调整后得分排序，取 max_stocks
    final_ranked = sorted(adjusted_scores.items(), key=lambda x: x[1], reverse=True)
    selected = final_ranked[: cfg["max_stocks"]]

    # 过滤掉负分的（除非不够 min_stocks）
    positive = [(c, s) for c, s in selected if s > 0]
    if len(positive) >= cfg["min_stocks"]:
        selected = positive

    if not selected:
        print("[optimizer] 优化后无有效股票")
        return {"date": sig_date, "regime": regime, "weights": {}, "stats": {}}

    # Softmax 归一化权重
    codes = [c for c, _ in selected]
    scores_arr = np.array([s for _, s in selected], dtype=np.float64)

    # 温度缩放
    scores_arr = scores_arr * cfg["softmax_temp"]
    scores_arr -= scores_arr.max()  # 数值稳定
    exp_scores = np.exp(scores_arr)
    weights = exp_scores / exp_scores.sum()

    # 截断到 max_weight
    for _ in range(10):  # 迭代截断
        over = weights > cfg["max_weight"]
        if not over.any():
            break
        excess = (weights[over] - cfg["max_weight"]).sum()
        weights[over] = cfg["max_weight"]
        under = ~over
        if under.any():
            weights[under] += excess * weights[under] / weights[under].sum()

    # 最终归一化
    weights = weights / weights.sum()

    weight_dict = {code: round(float(w), 6) for code, w in zip(codes, weights)}

    # 统计
    stats = {
        "n_stocks": len(weight_dict),
        "max_weight": round(float(weights.max()), 4),
        "min_weight": round(float(weights.min()), 4),
        "top5_weight": round(float(weights[:5].sum()), 4),
        "hhi": round(float((weights**2).sum()), 4),  # 集中度
        "avg_score": round(float(np.mean([all_scores.get(c, 0) for c in codes])), 6),
    }

    result = {
        "date": sig_date,
        "regime": regime,
        "model": signals.get("model", "unknown"),
        "config": cfg,
        "weights": weight_dict,
        "stats": stats,
    }

    # 保存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{sig_date}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(
        f"[optimizer] {sig_date} | {regime} | {stats['n_stocks']} stocks | "
        f"max_w={stats['max_weight']} | HHI={stats['hhi']} | top5={stats['top5_weight']}"
    )
    print(f"[optimizer] 保存: {out_path}")

    return result


if __name__ == "__main__":
    result = optimize()
    if result["weights"]:
        top10 = sorted(result["weights"].items(), key=lambda x: x[1], reverse=True)[:10]
        print("\nTop 10 持仓:")
        for code, w in top10:
            print(f"  {code}  {w:.4f} ({w * 100:.1f}%)")
