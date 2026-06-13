"""
因子 IC 分析 - 数据驱动确定最优权重
用 2018-2023 历史数据，对 InlineFactorGenerator 的 8 个因子分别计算 IC 序列
"""
import sys
import json
import numpy as np

sys.path.insert(0, "/home/tulin/quant")

from live.data_loader import load_market_data
from live.inline_factor_generator import InlineFactorGenerator
from factor.factor_analyzer import compute_ic

print("加载 2018-2023 市场数据...")
market_data = load_market_data("2018-01-01", "2023-12-31")
print(f"共 {len(market_data)} 个交易日")

gen = InlineFactorGenerator()
dates = sorted(market_data.keys())

# 每日：更新因子 → 记录因子值 → 计算次日收益
factor_history = {}  # {date: {factor_name: {code: value}}}
return_history = {}  # {date: {code: next_day_return}}

print("逐日计算因子值和收益率...")
for i, date in enumerate(dates):
    prices = market_data[date]
    gen.update(prices)

    # 记录当日因子值
    all_factors = gen._compute_all_factors()
    factor_history[date] = all_factors

    # 计算当日收益（相对前一日）用于与前一日因子做 IC
    if i > 0:
        prev_date = dates[i - 1]
        prev_prices = market_data[prev_date]
        returns = {}
        for code in prices:
            if code in prev_prices:
                prev_close = prev_prices[code]["close"]
                curr_close = prices[code]["close"]
                if prev_close > 0:
                    returns[code] = (curr_close - prev_close) / prev_close
        return_history[prev_date] = returns

    if (i + 1) % 200 == 0:
        print(f"  已处理 {i + 1}/{len(dates)} 天")

print(f"因子历史: {len(factor_history)} 天, 收益历史: {len(return_history)} 天")

# 对每个因子计算 IC 序列
factor_names = [
    "MOM_20", "MOM_60", "VOL_20", "REVERSAL_5",
    "MA_DEVIATION", "VOLUME_RATIO", "MOM_QUALITY", "VOL_CHANGE"
]

results = {}
for fname in factor_names:
    ic_list = []
    for date in dates[:-1]:  # 最后一天没有次日收益
        if date in factor_history and date in return_history:
            fvals = factor_history[date].get(fname, {})
            rets = return_history[date]
            ic = compute_ic(fvals, rets)
            if ic is not None:
                ic_list.append(ic)

    if ic_list:
        ics = np.array(ic_list)
        results[fname] = {
            "ic_mean": round(float(np.mean(ics)), 6),
            "ic_std": round(float(np.std(ics)), 6),
            "ir": round(float(np.mean(ics) / np.std(ics)), 4) if np.std(ics) > 0 else 0,
            "ic_positive_ratio": round(float(np.sum(ics > 0) / len(ics)), 4),
            "n_periods": len(ics)
        }

# 输出结果
print("\n" + "=" * 70)
print("因子 IC 分析结果（2018-2023）：")
print("=" * 70)
for fname, r in sorted(results.items(), key=lambda x: abs(x[1]["ic_mean"]), reverse=True):
    print(f"  {fname:16s}: IC={r['ic_mean']:+.6f}  IR={r['ir']:+.4f}  "
          f"IC>0={r['ic_positive_ratio']:.2%}  std={r['ic_std']:.6f}  n={r['n_periods']}")

# 计算 IC 加权最优权重
total_abs_ic = sum(abs(r["ic_mean"]) for r in results.values())
print("\n最优因子权重（IC绝对值归一化）：")
optimal_weights = {}
for fname in factor_names:
    if fname in results:
        w = abs(results[fname]["ic_mean"]) / total_abs_ic if total_abs_ic > 0 else 1 / len(results)
        optimal_weights[fname] = round(w, 4)
        print(f"  {fname:16s}: {w:.4f}")

# 保存结果
output = {"ic_results": results, "optimal_weights": optimal_weights}
with open("/home/tulin/quant/docs/factor_ic_analysis_2026-03-15.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n结果已保存: docs/factor_ic_analysis_2026-03-15.json")
