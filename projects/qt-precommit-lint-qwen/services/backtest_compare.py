"""
services/backtest_compare.py — 回测引擎对比

用同样的 ML 集成信号，分别跑:
  1. replay_engine_v5（现有事件驱动引擎）
  2. qlib_style_backtest（标准化回测，qlib 评估指标）

对比: 年化收益、Sharpe、最大回撤、Calmar、胜率
输出: data/backtest_compare/{date_range}.json + 飞书推送
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.replay_engine_v5 import ReplayEngineV5
from live.data_loader_fast import load_market_data_fast

OUTPUT_DIR = "data/backtest_compare"
SIGNAL_DIR = "data/signals"
FACTORS_PATH = "data/factors_latest.parquet"
FACTORS_FULL_PATH = "data/factors_full.parquet"


# ── Qlib-style 回测引擎 ──────────────────────────────────────


class QlibStyleBacktest:
    """
    标准化信号回测（模拟 qlib TopkDropout 策略）

    逻辑:
    - 每 rebalance_days 天调仓
    - 按 score 排序取 top_k，等权或优化权重
    - 计算每日收益率（用次日收盘价）
    - 输出标准指标
    """

    def __init__(
        self,
        scores: dict[str, dict[str, float]],  # {date: {ts_code: score}}
        prices: dict[str, dict[str, dict]],  # {date: {ts_code: {close, ...}}}
        top_k: int = 30,
        rebalance_days: int = 5,
        initial_capital: float = 1_000_000,
        commission: float = 0.001,  # 单边千一
        slippage: float = 0.001,  # 滑点千一
    ):
        self.scores = scores
        self.prices = prices
        self.top_k = top_k
        self.rebalance_days = rebalance_days
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

    def run(self) -> dict:
        dates = sorted(self.prices.keys())
        score_dates = sorted(self.scores.keys())

        capital = self.initial_capital
        holdings: dict[str, float] = {}  # {ts_code: weight}
        equity_curve = []
        daily_returns = []
        trade_count = 0
        day_since_rebalance = 0

        for i, date in enumerate(dates):
            day_prices = self.prices[date]

            # 调仓日
            if day_since_rebalance % self.rebalance_days == 0:
                # 找最近的信号日
                sig_date = None
                for sd in reversed(score_dates):
                    if sd <= date:
                        sig_date = sd
                        break

                if sig_date and sig_date in self.scores:
                    day_scores = self.scores[sig_date]
                    # 只选有行情的
                    available = {c: s for c, s in day_scores.items() if c in day_prices}
                    ranked = sorted(available.items(), key=lambda x: x[1], reverse=True)
                    new_holdings = {c: 1.0 / self.top_k for c, _ in ranked[: self.top_k]}

                    # 计算换手成本
                    old_set = set(holdings.keys())
                    new_set = set(new_holdings.keys())
                    turnover = len(old_set - new_set) + len(new_set - old_set)
                    cost = turnover * (self.commission + self.slippage) / self.top_k
                    capital *= 1 - cost
                    trade_count += turnover

                    holdings = new_holdings

            day_since_rebalance += 1

            # 计算当日组合收益
            if holdings and i > 0:
                prev_prices = self.prices[dates[i - 1]]
                port_return = 0.0
                valid_weight = 0.0

                for code, weight in holdings.items():
                    if code in day_prices and code in prev_prices:
                        prev_close = prev_prices[code].get("close", 0)
                        curr_close = day_prices[code].get("close", 0)
                        if prev_close > 0 and curr_close > 0:
                            ret = (curr_close - prev_close) / prev_close
                            port_return += weight * ret
                            valid_weight += weight

                if valid_weight > 0:
                    port_return = port_return / valid_weight * sum(holdings.values())

                capital *= 1 + port_return
                daily_returns.append(port_return)
            else:
                daily_returns.append(0.0)

            equity_curve.append(
                {
                    "date": date,
                    "equity": round(capital, 2),
                    "n_holdings": len(holdings),
                }
            )

        # 计算指标
        metrics = self._calc_metrics(daily_returns, equity_curve, trade_count)
        return {
            "equity_curve": equity_curve,
            "metrics": metrics,
            "daily_returns": daily_returns,
        }

    def _calc_metrics(self, returns, curve, trades) -> dict:
        r = np.array(returns)
        n_days = len(r)
        if n_days < 2:
            return {}

        # 年化收益
        total_return = curve[-1]["equity"] / self.initial_capital - 1
        ann_return = (1 + total_return) ** (252 / n_days) - 1

        # 年化波动率
        ann_vol = r.std() * np.sqrt(252)

        # Sharpe (无风险利率 2%)
        sharpe = (ann_return - 0.02) / ann_vol if ann_vol > 0 else 0

        # 最大回撤
        equities = [c["equity"] for c in curve]
        peak = equities[0]
        max_dd = 0
        for eq in equities:
            peak = max(peak, eq)
            dd = (peak - eq) / peak
            max_dd = max(max_dd, dd)

        # Calmar
        calmar = ann_return / max_dd if max_dd > 0 else 0

        # 胜率
        win_rate = (r > 0).sum() / n_days if n_days > 0 else 0

        return {
            "total_return": round(total_return, 4),
            "ann_return": round(ann_return, 4),
            "ann_vol": round(ann_vol, 4),
            "sharpe": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "calmar": round(calmar, 4),
            "win_rate": round(win_rate, 4),
            "n_days": n_days,
            "total_trades": trades,
        }


# ── 加载 ML 信号 ─────────────────────────────────────────────


def load_all_signals(start: str, end: str) -> dict[str, dict[str, float]]:
    """从 factors_full 生成每日 ML 信号（LGB+GRU 集成）"""
    # 先尝试从已有信号文件加载
    signals = {}
    if os.path.exists(SIGNAL_DIR):
        for f in sorted(os.listdir(SIGNAL_DIR)):
            if not f.endswith(".json"):
                continue
            date = f.replace(".json", "")
            if start <= date <= end:
                with open(os.path.join(SIGNAL_DIR, f)) as fh:
                    data = json.load(fh)
                    signals[date] = data.get("all_signals", {})
    return signals


def generate_signals_from_model(start: str, end: str) -> dict[str, dict[str, float]]:
    """用 LGB 模型对历史数据生成每日信号（用于回测期间没有信号文件的日期）"""
    from ml.models import BaseModel

    model_path = "ml/model_store/v1/global.pkl"
    if not os.path.exists(model_path):
        print("[backtest] 无 LGB 模型，跳过信号生成")
        return {}

    model = BaseModel.load(model_path)
    meta_path = "ml/model_store/v1/meta.json"
    with open(meta_path) as f:
        feature_names = json.load(f).get("feature_names", [])

    # 加载因子数据
    path = FACTORS_FULL_PATH if os.path.exists(FACTORS_FULL_PATH) else FACTORS_PATH
    print(f"[backtest] 加载因子: {path}")

    import pyarrow.parquet as pq
    from datetime import date as _date

    signals = {}
    start_year = int(start[:4])
    end_year = int(end[:4])

    for year in range(start_year, end_year + 1):
        filters = [
            ("trade_date", ">=", _date(year, 1, 1)),
            ("trade_date", "<=", _date(year, 12, 31)),
        ]
        try:
            df = pd.read_parquet(path, filters=filters)
        except Exception:
            df = pd.read_parquet(path)
            df = df[pd.to_datetime(df["trade_date"]).dt.year == year]

        if df.empty:
            continue

        df["trade_date"] = pd.to_datetime(df["trade_date"])

        for dt, grp in df.groupby("trade_date"):
            date_str = dt.strftime("%Y-%m-%d")
            if date_str < start or date_str > end:
                continue

            feat_cols = [c for c in feature_names if c in grp.columns]
            X = grp[feat_cols].values.astype(np.float32)
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
            scores = model.predict(X)
            signals[date_str] = dict(zip(grp["ts_code"].values, [float(s) for s in scores]))

        del df
        print(f"[backtest] {year}: {sum(1 for d in signals if d.startswith(str(year)))} 天信号")

    return signals


# ── 主函数 ────────────────────────────────────────────────────


def compare(
    start: str = "2025-07-01",
    end: str = "2026-03-13",
    top_k: int = 30,
    rebalance_days: int = 5,
):
    print(f"[backtest_compare] {start} ~ {end}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 加载行情
    t0 = time.time()
    market_data = load_market_data_fast(start, end)
    print(f"  行情: {len(market_data)} 天 ({time.time() - t0:.1f}s)")

    # 2. 加载/生成信号
    signals = load_all_signals(start, end)
    if len(signals) < 10:
        print(f"  信号文件不足({len(signals)}天)，从模型生成...")
        model_signals = generate_signals_from_model(start, end)
        signals.update(model_signals)
    print(f"  信号: {len(signals)} 天")

    if not signals:
        print("[backtest_compare] 无信号，终止")
        return

    # 3. Qlib-style 回测
    print("\n── Qlib-style 回测 ──")
    t1 = time.time()
    qlib_bt = QlibStyleBacktest(
        scores=signals,
        prices=market_data,
        top_k=top_k,
        rebalance_days=rebalance_days,
    )
    qlib_result = qlib_bt.run()
    print(f"  耗时: {time.time() - t1:.1f}s")
    print(f"  指标: {json.dumps(qlib_result['metrics'], indent=2)}")

    # 4. Replay Engine V5 回测（纯 Factor 模式，与 Qlib-style 公平对比）
    print("\n── Replay Engine V5 回测（纯 Factor 模式）──")
    t2 = time.time()
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
    print(f"  耗时: {time.time() - t2:.1f}s")

    # V5 指标计算
    v5_equities = [c["equity"] for c in v5_curve]
    v5_returns = []
    for i in range(1, len(v5_equities)):
        v5_returns.append((v5_equities[i] - v5_equities[i - 1]) / v5_equities[i - 1])

    v5_r = np.array(v5_returns)
    n = len(v5_r)
    v5_total = v5_equities[-1] / v5_equities[0] - 1 if v5_equities else 0
    v5_ann = (1 + v5_total) ** (252 / n) - 1 if n > 0 else 0
    v5_vol = v5_r.std() * np.sqrt(252) if n > 0 else 0
    v5_sharpe = (v5_ann - 0.02) / v5_vol if v5_vol > 0 else 0

    peak = v5_equities[0]
    v5_maxdd = 0
    for eq in v5_equities:
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
    print("\n── 对比 ──")
    comparison = {
        "period": f"{start} ~ {end}",
        "qlib_style": qlib_result["metrics"],
        "replay_v5": v5_metrics,
        "diff": {},
    }

    for key in ["total_return", "ann_return", "sharpe", "max_drawdown", "calmar"]:
        q = qlib_result["metrics"].get(key, 0)
        v = v5_metrics.get(key, 0)
        comparison["diff"][key] = round(q - v, 4)
        print(f"  {key:15s}  qlib={q:+.4f}  v5={v:+.4f}  diff={q - v:+.4f}")

    # 保存
    out_path = os.path.join(OUTPUT_DIR, f"{start}_{end}.json")
    with open(out_path, "w") as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    print(f"\n  保存: {out_path}")

    return comparison


if __name__ == "__main__":
    compare()
