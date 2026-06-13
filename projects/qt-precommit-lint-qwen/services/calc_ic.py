"""
IC 分析 — 验证 ML 信号的预测能力
IC = 信号分数与未来 N 日收益的 Spearman 相关系数
ICIR = IC 均值 / IC 标准差（越高越稳定）

用法:
  python services/calc_ic.py
  python services/calc_ic.py --forward-days 1 5 10 20
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PG_CONFIG


def load_signal(signal_path: str) -> pd.DataFrame:
    """加载信号文件，返回 DataFrame(ts_code, score)"""
    d = json.loads(Path(signal_path).read_text())
    sigs = d.get("all_signals", d)
    df = pd.DataFrame(list(sigs.items()), columns=["ts_code", "score"])
    # 提取信号日期
    date_str = Path(signal_path).stem  # e.g. "2026-03-25"
    df["signal_date"] = date_str
    return df


def load_forward_returns(signal_date: str, forward_days: list[int], conn) -> pd.DataFrame:
    """从 daily_price 加载信号日期后 N 日的收益率"""
    # 获取信号日期之后的交易日
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT trade_date FROM daily_price
        WHERE trade_date > %s
        ORDER BY trade_date
        LIMIT %s
    """,
        (signal_date, max(forward_days) + 5),
    )
    future_dates = [str(r[0]) for r in cur.fetchall()]

    if not future_dates:
        return pd.DataFrame()

    # 获取信号日当天收盘价
    cur.execute(
        """
        SELECT ts_code, close FROM daily_price
        WHERE trade_date = %s AND close > 0
    """,
        (signal_date,),
    )
    base_prices = {r[0]: float(r[1]) for r in cur.fetchall()}

    if not base_prices:
        return pd.DataFrame()

    results = {"ts_code": list(base_prices.keys())}

    for n in forward_days:
        if n > len(future_dates):
            print(f"  ⚠️  forward_{n}d: 数据不足（只有 {len(future_dates)} 个未来交易日）")
            continue

        target_date = future_dates[n - 1]
        cur.execute(
            """
            SELECT ts_code, close FROM daily_price
            WHERE trade_date = %s AND close > 0
        """,
            (target_date,),
        )
        future_prices = {r[0]: float(r[1]) for r in cur.fetchall()}

        col = f"ret_{n}d"
        results[col] = [
            (future_prices.get(code, np.nan) / base_prices[code] - 1) if code in future_prices else np.nan
            for code in results["ts_code"]
        ]
        print(f"  forward_{n}d: target_date={target_date}, {len(future_prices)} stocks")

    return pd.DataFrame(results)


def calc_ic(signal_df: pd.DataFrame, return_df: pd.DataFrame, forward_days: list[int]) -> dict:
    """计算 IC（Spearman 相关系数）"""
    merged = signal_df.merge(return_df, on="ts_code", how="inner")
    merged = merged.dropna(subset=["score"])

    results = {}
    for n in forward_days:
        col = f"ret_{n}d"
        if col not in merged.columns:
            continue
        sub = merged[["score", col]].dropna()
        if len(sub) < 50:
            print(f"  ⚠️  forward_{n}d: 样本不足 ({len(sub)} 只)")
            continue

        # Spearman IC
        ic = sub["score"].corr(sub[col], method="spearman")

        # 分组收益（Top 20% vs Bottom 20%）
        sub = sub.copy()
        sub["rank"] = sub["score"].rank(pct=True)
        top = sub[sub["rank"] >= 0.8][col].mean()
        bottom = sub[sub["rank"] <= 0.2][col].mean()
        spread = top - bottom

        results[n] = {
            "ic": round(ic, 4),
            "n_stocks": len(sub),
            "top20_ret": round(top * 100, 3),
            "bottom20_ret": round(bottom * 100, 3),
            "spread": round(spread * 100, 3),
        }

    return results


def run(forward_days: list[int] = None):
    if forward_days is None:
        forward_days = [1, 3, 5, 10, 20]

    signals_dir = Path("/home/tulin/quant/data/signals")
    signal_files = sorted(signals_dir.glob("*.json"), reverse=True)

    if not signal_files:
        print("❌ 没有找到信号文件")
        return

    conn = psycopg.connect(**PG_CONFIG)

    all_results = []

    print(f"\n{'=' * 60}")
    print(f"IC 分析报告 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'=' * 60}")

    for sig_file in signal_files:
        signal_date = sig_file.stem
        print(f"\n📅 信号日期: {signal_date}  ({sig_file.name})")

        # 加载信号
        sig_df = load_signal(str(sig_file))
        print(f"  信号股票数: {len(sig_df)}")
        print(f"  分数范围: [{sig_df['score'].min():.4f}, {sig_df['score'].max():.4f}]")
        print(f"  分数均值: {sig_df['score'].mean():.4f}  标准差: {sig_df['score'].std():.4f}")

        # 加载 forward return
        print(f"  加载未来收益...")
        ret_df = load_forward_returns(signal_date, forward_days, conn)

        if ret_df.empty:
            print(f"  ⚠️  无未来数据，跳过")
            continue

        # 计算 IC
        ic_results = calc_ic(sig_df, ret_df, forward_days)

        if not ic_results:
            print(f"  ⚠️  IC 计算失败")
            continue

        print(f"\n  {'N日':>6} {'IC':>8} {'Top20%':>10} {'Bot20%':>10} {'Spread':>10} {'样本数':>8}")
        print(f"  {'-' * 56}")
        for n, r in ic_results.items():
            ic_val = r["ic"]
            flag = "✅" if abs(ic_val) >= 0.05 else ("⚠️ " if abs(ic_val) >= 0.02 else "❌")
            print(
                f"  {n:>4}d  {ic_val:>8.4f} {r['top20_ret']:>9.3f}% {r['bottom20_ret']:>9.3f}% {r['spread']:>9.3f}% {r['n_stocks']:>8}  {flag}"
            )

        all_results.append({"date": signal_date, "ic": ic_results})

    conn.close()

    # 汇总 ICIR（如果有多个信号日期）
    if len(all_results) >= 2:
        print(f"\n{'=' * 60}")
        print(f"ICIR 汇总（{len(all_results)} 个信号日期）")
        print(f"{'=' * 60}")
        for n in forward_days:
            ics = [r["ic"].get(n, {}).get("ic") for r in all_results if n in r["ic"]]
            ics = [x for x in ics if x is not None]
            if len(ics) >= 2:
                icir = np.mean(ics) / (np.std(ics) + 1e-8)
                print(f"  {n}d: IC均值={np.mean(ics):.4f}  ICIR={icir:.2f}  ({len(ics)} 样本)")

    print(f"\n{'=' * 60}")
    print("判断标准:")
    print("  ✅ |IC| >= 0.05 且 ICIR >= 0.5 → 模型有效")
    print("  ⚠️  |IC| 0.02~0.05 → 弱信号，可用但需谨慎")
    print("  ❌ |IC| < 0.02 → 模型基本无效，需重训")
    print(f"{'=' * 60}\n")

    return all_results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--forward-days", nargs="+", type=int, default=[1, 3, 5, 10, 20])
    args = parser.parse_args()
    run(forward_days=args.forward_days)
