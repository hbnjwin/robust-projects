"""
统一回测入口 - 使用 ReplayEngineV3 作为唯一回测引擎
用法: python unified_backtest.py --start 2020-01-01 --end 2024-12-31 --capital 1000000
"""

import argparse
import json
import sys
import numpy as np
from datetime import datetime

sys.path.insert(0, "/home/tulin/quant")

from live.replay_engine_v3 import ReplayEngineV3
from live.data_loader import load_market_data
from analytics.metrics_v2 import (
    max_drawdown,
    annual_return,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    max_consecutive_loss_days,
)


def run_unified_backtest(start_date, end_date, initial_capital=1_000_000):
    """运行统一回测"""
    print(f"加载市场数据: {start_date} ~ {end_date}")
    market_data = load_market_data(start_date, end_date)

    if not market_data:
        print("无市场数据，退出")
        return None

    print(f"交易日数: {len(market_data)}")
    print(f"初始资金: {initial_capital:,.0f}")

    engine = ReplayEngineV3(
        market_data=market_data, start_date=start_date, end_date=end_date, initial_capital=initial_capital
    )

    equity_curve = engine.run()

    if not equity_curve:
        print("回测无结果")
        return None

    equities = np.array([e["equity"] for e in equity_curve])
    dates = [e["date"] for e in equity_curve]

    # 计算指标
    results = {
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": initial_capital,
        "final_equity": round(equities[-1], 2),
        "total_return": round(equities[-1] / equities[0] - 1, 4),
        "annual_return": round(annual_return(equities), 4),
        "max_drawdown": round(max_drawdown(equities), 4),
        "sharpe_ratio": round(sharpe_ratio(equities), 4),
        "sortino_ratio": round(sortino_ratio(equities), 4),
        "calmar_ratio": round(calmar_ratio(equities), 4),
        "max_consecutive_ls": max_consecutive_loss_days(equities),
        "trade_days": len(equities),
    }

    # 各策略账户统计
    for name, account in engine.master.strategy_accounts.items():
        results[f"{name}_equity"] = round(account.total_equity, 2)
        results[f"{name}_trades"] = len(account.trade_log)
        results[f"{name}_max_dd"] = round(account.max_drawdown, 4)

    # 输出
    print("\n" + "=" * 50)
    print("统一回测结果")
    print("=" * 50)
    for k, v in results.items():
        print(f"  {k}: {v}")

    return results


def main():
    parser = argparse.ArgumentParser(description="统一回测入口")
    parser.add_argument("--start", default="2020-01-01", help="起始日期")
    parser.add_argument("--end", default="2024-12-31", help="结束日期")
    parser.add_argument("--capital", type=int, default=1_000_000, help="初始资金")
    args = parser.parse_args()

    run_unified_backtest(args.start, args.end, args.capital)


if __name__ == "__main__":
    main()
