"""
LowVol 止损参数网格搜索
目标：找到在 2018 熊市不恶化、同时保持其他场景改善的参数组合
"""

import sys
import json
import numpy as np

sys.path.insert(0, "/home/tulin/quant")

from live.data_loader import load_market_data
from live.replay_engine_v3 import ReplayEngineV3
from analytics.metrics_v2 import max_drawdown, annual_return, sharpe_ratio


# 需要 monkey-patch LowVolStrategy 的参数
def run_scenario_with_params(start, end, stop_loss, cooldown, rebalance_interval):
    """用指定参数跑单个场景"""
    market_data = load_market_data(start, end)
    if not market_data:
        return None

    engine = ReplayEngineV3(market_data=market_data, start_date=start, end_date=end, initial_capital=1_000_000)

    # 覆盖 LowVol 策略参数
    engine.lowvol.stop_loss_pct = stop_loss
    engine.lowvol.cooldown_days = cooldown
    engine.lowvol.rebalance_interval = rebalance_interval

    equity_curve = engine.run()
    if not equity_curve:
        return None

    equities = np.array([e["equity"] for e in equity_curve])
    return {
        "total_return": round((equities[-1] / equities[0] - 1) * 100, 2),
        "max_drawdown": round(max_drawdown(equities) * 100, 2),
        "sharpe": round(sharpe_ratio(equities), 4),
    }


SCENARIOS = {
    "bear_2018": ("2018-01-02", "2018-07-02"),
    "covid_2020": ("2020-02-03", "2020-08-03"),
    "top_2021": ("2021-02-18", "2021-08-18"),
    "downtrend_2022": ("2022-04-01", "2022-10-01"),
    "ai_2023": ("2023-01-03", "2023-07-03"),
}

# 参数网格
STOP_LOSS_VALUES = [0.10, 0.15, 0.20, 0.25, 0.30]
COOLDOWN_VALUES = [3, 5, 7, 10]
REBALANCE_VALUES = [5]  # 固定调仓周期

results = []

total = len(STOP_LOSS_VALUES) * len(COOLDOWN_VALUES)
count = 0

for sl in STOP_LOSS_VALUES:
    for cd in COOLDOWN_VALUES:
        count += 1
        print("--- [{}/{}] stop_loss={} cooldown={} ---".format(count, total, sl, cd))

        row = {"stop_loss": sl, "cooldown": cd}
        total_sharpe = 0
        worst_return = 999

        for tag, (start, end) in SCENARIOS.items():
            r = run_scenario_with_params(start, end, sl, cd, 5)
            if r:
                row[tag + "_ret"] = r["total_return"]
                row[tag + "_dd"] = r["max_drawdown"]
                row[tag + "_sharpe"] = r["sharpe"]
                total_sharpe += r["sharpe"]
                worst_return = min(worst_return, r["total_return"])
            else:
                row[tag + "_ret"] = None

        row["avg_sharpe"] = round(total_sharpe / 5, 4)
        row["worst_return"] = worst_return
        # 综合评分：平均Sharpe - 最差场景惩罚
        row["score"] = round(row["avg_sharpe"] + worst_return / 100, 4)

        results.append(row)
        print("  avg_spe={} worst_ret={} score={}".format(row["avg_sharpe"], row["worst_return"], row["score"]))

# 按综合评分排序
results.sort(key=lambda x: x["score"], reverse=True)

print("\n" + "=" * 80)
print("TOP 5 参数组合")
print("=" * 80)
for i, r in enumerate(results[:5]):
    print(
        "\n#{}: stop_loss={} cooldown={} | score={} avg_sharpe={} worst_ret={}".format(
            i + 1, r["stop_loss"], r["cooldown"], r["score"], r["avg_sharpe"], r["worst_return"]
        )
    )
    for tag in SCENARIOS:
        print(
            "  {}: ret={} dd={} sharpe={}".format(tag, r.get(tag + "_ret"), r.get(tag + "_dd"), r.get(tag + "_sharpe"))
        )

# 保存完整结果
with open("docs/lowvol_param_grid_2026-03-15.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\n完整结果已保存: docs/lowvol_param_grid_2026-03-15.json")

# 输出最优参数
best = results[0]
print("\n推荐参数: stop_loss={} cooldown={}".format(best["stop_loss"], best["cooldown"]))
