"""
五个典型场景回测 - 使用修复后的 ReplayEngineV3 + metrics_v2
验证架构统一和缺陷修复后的系统效果
"""

import sys
import json
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

SCENARIOS = {
    "bear_2018": {"start": "2018-01-02", "end": "2018-07-02", "desc": "2018熊市"},
    "covid_2020": {"start": "2020-02-03", "end": "2020-08-03", "desc": "2020疫情冲击"},
    "top_2021": {"start": "2021-02-18", "end": "2021-08-18", "desc": "2021市场见顶"},
    "downtrend_2022": {"start": "2022-04-01", "end": "2022-10-01", "desc": "2022持续下行"},
    "ai_start_2023": {"start": "2023-01-03", "end": "2023-07-03", "desc": "2023AI行情启动"},
}

INITIAL_CAPITAL = 1_000_000


def run_scenario(tag, start, end):
    """运行单个场景"""
    market_data = load_market_data(start, end)

    if not market_data:
        return None

    engine = ReplayEngineV3(market_data=market_data, start_date=start, end_date=end, initial_capital=INITIAL_CAPITAL)

    equity_curve = engine.run()

    if not equity_curve:
        return None

    equities = np.array([e["equity"] for e in equity_curve])

    result = {
        "final_equity": round(equities[-1], 2),
        "total_return": round((equities[-1] / equities[0] - 1) * 100, 2),
        "annual_return": round(annual_return(equities) * 100, 2),
        "max_drawdown": round(max_drawdown(equities) * 100, 2),
        "sharpe": round(sharpe_ratio(equities), 4),
        "sortino": round(sortino_ratio(equities), 4),
        "calmar": round(calmar_ratio(equities), 4),
        "max_loss_streak": max_consecutive_loss_days(equities),
        "trade_days": len(equities),
    }

    # 各策略账户
    for name, account in engine.master.strategy_accounts.items():
        result[name + "_equity"] = round(account.total_equity, 2)
        result[name + "_trades"] = len(account.trade_log)
        result[name + "_max_dd"] = round(account.max_drawdown * 100, 2)

    return result


def main():
    print("=" * 70)
    print("五个典型场景回测 - 修复后系统验证")
    print("初始资金: {:,.0f}".format(INITIAL_CAPITAL))
    print("=" * 70)

    all_results = {}

    for tag, cfg in SCENARIOS.items():
        print("\n--- {} ({}) ---".format(cfg["desc"], tag))
        print("区间: {} ~ {}".format(cfg["start"], cfg["end"]))

        result = run_scenario(tag, cfg["start"], cfg["end"])

        if result is None:
            print("  无数据，跳过")
            continue

        all_results[tag] = result
        result["desc"] = cfg["desc"]
        result["start"] = cfg["start"]
        result["end"] = cfg["end"]

        print("  最终权益: {:,.2f}".format(result["final_equity"]))
        print("  总收益率: {}%".format(result["total_return"]))
        print("  年化收益: {}%".format(result["annual_return"]))
        print("  最大回撤: {}%".format(result["max_drawdown"]))
        print("  Sharpe:   {}".format(result["sharpe"]))
        print("  Sortino:  {}".format(result["sortino"]))
        print("  Calmar:   {}".format(result["calmar"]))
        print("  最大连亏: {} 天".format(result["max_loss_streak"]))
        print("  交易日数: {}".format(result["trade_days"]))

        for name in ["Trend", "LowVol", "Cash"]:
            if name + "_equity" in result:
                print(
                    "  [{}] 权益={:,.2f} 交易={} 最大回撤={}%".format(
                        name, result[name + "_equity"], result[name + "_trades"], result[name + "_max_dd"]
                    )
                )

    # 汇总表
    print("\n" + "=" * 70)
    print("汇总对比")
    print("=" * 70)
    print(
        "{:<20} {:>12} {:>10} {:>10} {:>8} {:>8}".format("场景", "最终权益", "总收益%", "最大回撤%", "Sharpe", "Calmar")
    )
    print("-" * 70)
    for tag, r in all_results.items():
        print(
            "{:<20} {:>12,.2f} {:>10} {:>10} {:>8} {:>8}".format(
                r["desc"], r["final_equity"], r["total_return"], r["max_drawdown"], r["sharpe"], r["calmar"]
            )
        )

    # 保存结果
    output_path = "docs/scenario_test_post_fix_2026-03-15.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False, default=str)
    print("\n结果已保存: {}".format(output_path))


if __name__ == "__main__":
    main()
