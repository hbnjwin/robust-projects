"""
蒙特卡洛策略压力测试
随机选取历史时间窗口，三策略模拟交易，记录每日明细到 PG，生成分析报告。
后台驻留，每 30 分钟运行一次。

用法:
    cd /home/tulin/quant
    python testing/monte_carlo_sim.py              # 单次运行
    python testing/monte_carlo_sim.py --daemon      # 后台驻留
    python testing/monte_carlo_sim.py --count 10    # 连续跑10次
"""
import sys
import os
import json
import time
import random
import argparse
import functools
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

# 强制 stdout 不缓冲
print = functools.partial(print, flush=True)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import PG_CONFIG
from live.data_loader_fast import load_market_data_fast
from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.regime_detector_v2 import RegimeDetectorV2
from strategies.factor_strategy import FactorStrategy

# ── 配置 ──
INITIAL_CAPITAL = 1_000_000
TREND_RATIO = 0.15
LOWVOL_RATIO = 0.15
FACTOR_RATIO = 0.50
CASH_RATIO = 0.20

REPORT_DIR = "testing/sim_reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# ML 信号（全局加载一次）
_ml_signals = None


def load_ml_signals():
    global _ml_signals
    if _ml_signals is None:
        sig_df = pd.read_parquet("data/ml_signals.parquet")
        _ml_signals = {}
        for d, g in sig_df.groupby("trade_date"):
            _ml_signals[d] = dict(zip(g["ts_code"], g["score"]))
        print(f"[sim] ML signals loaded: {len(_ml_signals)} days")
    return _ml_signals


def random_window():
    """随机选取起始日期和持仓时长"""
    # 起始日期: 2018-06-01 ~ 2025-09-01
    start_pool_begin = datetime(2018, 6, 1)
    start_pool_end = datetime(2025, 9, 1)
    delta = (start_pool_end - start_pool_begin).days
    start = start_pool_begin + timedelta(days=random.randint(0, delta))

    # 持仓时长: 1/2/3/6 个月
    months = random.choice([1, 2, 3, 6])
    end = start + timedelta(days=months * 30)

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), months


def gen_sim_id():
    now = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = random.randint(100, 999)
    return f"SIM-{now}-{rand}"


def calc_sharpe(equities):
    if len(equities) < 2:
        return 0.0
    rets = []
    for i in range(1, len(equities)):
        prev = equities[i - 1]
        if prev > 0:
            rets.append((equities[i] - prev) / prev)
    if len(rets) < 2:
        return 0.0
    std = np.std(rets)
    if std == 0:
        return 0.0
    return float(np.mean(rets) / std * np.sqrt(240))


def run_single_sim(start_date=None, end_date=None, months=None):
    """运行一次模拟"""
    if start_date is None:
        start_date, end_date, months = random_window()

    sim_id = gen_sim_id()
    ml_signals = load_ml_signals()

    print(f"\n{'='*60}")
    print(f"  {sim_id}")
    print(f"  Window: {start_date} ~ {end_date} ({months}M)")
    print(f"{'='*60}")

    # 加载行情（含预热期）
    warmup_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=90)).strftime("%Y-%m-%d")
    market_data = load_market_data_fast(warmup_start, end_date)
    if not market_data:
        print("  [SKIP] No market data")
        return None

    dates = sorted(market_data.keys())
    sim_dates = [d for d in dates if d >= start_date and d <= end_date]
    warmup_dates = [d for d in dates if d < start_date]

    if len(sim_dates) < 5:
        print(f"  [SKIP] Only {len(sim_dates)} trading days")
        return None

    print(f"  Warmup: {len(warmup_dates)} days, Sim: {len(sim_dates)} days")

    # 初始化策略和账户
    trend_acc = StrategyAccount("Trend", INITIAL_CAPITAL * TREND_RATIO)
    lowvol_acc = StrategyAccount("LowVol", INITIAL_CAPITAL * LOWVOL_RATIO)
    factor_acc = StrategyAccount("Factor", INITIAL_CAPITAL * FACTOR_RATIO)

    trend_eng = ExecutionEngine(trend_acc)
    lowvol_eng = ExecutionEngine(lowvol_acc)
    factor_eng = ExecutionEngine(factor_acc)

    trend = TrendStrategyV2()
    lowvol = LowVolStrategy()
    det = RegimeDetectorV2()
    factor_strat = FactorStrategy(factor_scores=ml_signals, top_n=15, rebalance_days=5)

    # 预热
    for date in warmup_dates:
        prices = market_data[date]
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            det.update(np.mean(closes), 0)
        trend.generate(date, prices)
        lowvol.set_regime(det.detect())
        lowvol.generate(date, prices)
        factor_strat.generate(date, prices)

    # 模拟交易
    daily_records = []
    all_trades = []
    all_positions = []
    regime_counts = {"BULL": 0, "CRISIS": 0, "NEUTRAL": 0}
    prev_equity = INITIAL_CAPITAL

    for day_num, date in enumerate(sim_dates, 1):
        prices = market_data[date]
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            det.update(np.mean(closes), 0)
        regime = det.detect()
        regime_counts[regime] = regime_counts.get(regime, 0) + 1

        lowvol.set_regime(regime)
        trend_signals = trend.generate(date, prices)
        lowvol_signals = lowvol.generate(date, prices)
        factor_signals = factor_strat.generate(date, prices)

        if regime == "CRISIS":
            trend_signals = [{"action": "sell", "ts_code": c} for c in list(trend_acc.positions.keys())]
            lowvol_signals = [{"action": "sell", "ts_code": c} for c in list(lowvol_acc.positions.keys())]
            factor_signals = [{"action": "sell", "ts_code": c} for c in list(factor_acc.positions.keys())]

        trend_eng.queue_orders(trend_signals)
        lowvol_eng.queue_orders(lowvol_signals)
        factor_eng.queue_orders(factor_signals)

        trend_eng.execute(prices, date=date)
        lowvol_eng.execute(prices, date=date)
        factor_eng.execute(prices, date=date)

        trend_acc.mark_to_market(prices)
        lowvol_acc.mark_to_market(prices)
        factor_acc.mark_to_market(prices)

        total_eq = (trend_acc.total_equity + lowvol_acc.total_equity
                    + factor_acc.total_equity + INITIAL_CAPITAL * CASH_RATIO)
        daily_ret = (total_eq - prev_equity) / prev_equity if prev_equity > 0 else 0
        prev_equity = total_eq

        # 记录每日快照
        daily_records.append({
            "sim_id": sim_id, "trade_date": date, "day_num": day_num,
            "regime": regime, "total_equity": round(total_eq, 2),
            "daily_return": round(daily_ret, 6),
            "trend_equity": round(trend_acc.total_equity, 2),
            "lowvol_equity": round(lowvol_acc.total_equity, 2),
            "factor_equity": round(factor_acc.total_equity, 2),
            "trend_positions": len(trend_acc.positions),
            "lowvol_positions": len(lowvol_acc.positions),
            "factor_positions": len(factor_acc.positions),
        })

        # 记录交易明细
        for strat_name, acc in [("Trend", trend_acc), ("LowVol", lowvol_acc), ("Factor", factor_acc)]:
            for t in acc.trade_log:
                all_trades.append({
                    "sim_id": sim_id, "trade_date": date,
                    "strategy": strat_name, "ts_code": t["code"],
                    "action": t["action"], "price": t["price"],
                    "shares": t["shares"],
                    "amount": round(t["price"] * t["shares"], 2),
                    "fee": round(t["fee"], 4),
                    "reason": t.get("reason", ""),
                })
            acc.trade_log.clear()

        # 记录持仓明细
        for strat_name, acc in [("Trend", trend_acc), ("LowVol", lowvol_acc), ("Factor", factor_acc)]:
            for code, pos in acc.positions.items():
                mkt_price = prices.get(code, {}).get("close", 0)
                avg_cost = pos.get("avg_cost", 0)
                shares = pos.get("shares", 0)
                mkt_val = round(mkt_price * shares, 2)
                pnl = round((mkt_price / avg_cost - 1) * 100, 4) if avg_cost > 0 else 0
                buy_date = pos.get("buy_date", date)
                hold = 0
                try:
                    hold = (datetime.strptime(date, "%Y-%m-%d") - datetime.strptime(str(buy_date), "%Y-%m-%d")).days
                except Exception:
                    pass
                all_positions.append({
                    "sim_id": sim_id, "trade_date": date,
                    "strategy": strat_name, "ts_code": code,
                    "shares": shares, "avg_cost": round(avg_cost, 4),
                    "market_price": round(mkt_price, 4),
                    "market_value": mkt_val, "pnl_pct": pnl,
                    "hold_days": hold,
                })

    # 计算结果
    equities = [INITIAL_CAPITAL] + [r["total_equity"] for r in daily_records]
    final_eq = equities[-1]
    total_ret = (final_eq / INITIAL_CAPITAL - 1) * 100
    days = len(sim_dates)
    annual_ret = total_ret / days * 240 if days > 0 else 0
    max_dd = 0
    peak = INITIAL_CAPITAL
    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak
        if dd > max_dd:
            max_dd = dd

    def strat_stats(acc, capital):
        ret = (acc.total_equity / capital - 1) * 100 if capital > 0 else 0.0
        return round(ret, 4), round(acc.max_drawdown * 100, 4)

    t_ret, t_dd = strat_stats(trend_acc, INITIAL_CAPITAL * TREND_RATIO)
    l_ret, l_dd = strat_stats(lowvol_acc, INITIAL_CAPITAL * LOWVOL_RATIO)
    f_ret, f_dd = strat_stats(factor_acc, INITIAL_CAPITAL * FACTOR_RATIO)

    t_sharpe = calc_sharpe([INITIAL_CAPITAL * TREND_RATIO] + [r["trend_equity"] for r in daily_records])
    l_sharpe = calc_sharpe([INITIAL_CAPITAL * LOWVOL_RATIO] + [r["lowvol_equity"] for r in daily_records])
    f_sharpe = calc_sharpe([INITIAL_CAPITAL * FACTOR_RATIO] + [r["factor_equity"] for r in daily_records])
    total_sharpe = calc_sharpe(equities)

    # 写入 PG
    conn = psycopg.connect(**PG_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO sim_runs (sim_id, start_date, end_date, duration_months, trading_days,
            final_equity, total_return, annual_return, max_drawdown, sharpe,
            trend_return, trend_dd, trend_sharpe,
            lowvol_return, lowvol_dd, lowvol_sharpe,
            factor_return, factor_dd, factor_sharpe,
            bull_days, crisis_days, neutral_days)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (sim_id, start_date, end_date, months, days,
          round(final_eq, 2), round(total_ret, 4), round(annual_ret, 4),
          round(max_dd * 100, 4), round(total_sharpe, 4),
          t_ret, t_dd, round(t_sharpe, 4),
          l_ret, l_dd, round(l_sharpe, 4),
          f_ret, f_dd, round(f_sharpe, 4),
          regime_counts.get("BULL", 0), regime_counts.get("CRISIS", 0),
          regime_counts.get("NEUTRAL", 0)))

    # 批量写入每日快照
    for r in daily_records:
        cur.execute("""
            INSERT INTO sim_daily (sim_id, trade_date, day_num, regime,
                total_equity, daily_return, drawdown,
                trend_equity, lowvol_equity, factor_equity,
                trend_positions, lowvol_positions, factor_positions)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (r["sim_id"], r["trade_date"], r["day_num"], r["regime"],
              r["total_equity"], r["daily_return"], 0,
              r["trend_equity"], r["lowvol_equity"], r["factor_equity"],
              r["trend_positions"], r["lowvol_positions"], r["factor_positions"]))

    # 批量写入交易明细
    for t in all_trades:
        cur.execute("""
            INSERT INTO sim_trades (sim_id, trade_date, strategy, ts_code,
                action, price, shares, amount, fee, reason)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (t["sim_id"], t["trade_date"], t["strategy"], t["ts_code"],
              t["action"], t["price"], t["shares"], t["amount"], t["fee"], t["reason"]))

    # 批量写入持仓明细
    for p in all_positions:
        cur.execute("""
            INSERT INTO sim_positions (sim_id, trade_date, strategy, ts_code,
                shares, avg_cost, market_price, market_value, pnl_pct, hold_days)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (sim_id, trade_date, strategy, ts_code) DO NOTHING
        """, (p["sim_id"], p["trade_date"], p["strategy"], p["ts_code"],
              p["shares"], p["avg_cost"], p["market_price"],
              p["market_value"], p["pnl_pct"], p["hold_days"]))

    # 自动打标签
    tags = []
    is_notable = False

    # 高收益
    if total_ret > 10:
        tags.append("高收益")
        is_notable = True
    # 大亏损
    if total_ret < -10:
        tags.append("大亏损")
        is_notable = True
    # 高回撤
    if max_dd > 0.15:
        tags.append("高回撤")
        is_notable = True
    # 低回撤高收益（理想场景）
    if total_ret > 5 and max_dd < 0.08:
        tags.append("理想场景")
        is_notable = True
    # Crisis 主导
    if regime_counts.get("CRISIS", 0) > days * 0.3:
        tags.append("危机主导")
        is_notable = True
    # Bull 主导
    if regime_counts.get("BULL", 0) > days * 0.7:
        tags.append("牛市主导")
    # Factor 策略显著优于其他
    if f_ret > t_ret + 5 and f_ret > l_ret + 5:
        tags.append("Factor领先")
        is_notable = True
    # Trend 策略显著优于其他
    if t_ret > f_ret + 5 and t_ret > l_ret + 5:
        tags.append("Trend领先")
    # 三策略全亏
    if t_ret < 0 and l_ret < 0 and f_ret < 0:
        tags.append("全线亏损")
    # 三策略全赚
    if t_ret > 0 and l_ret > 0 and f_ret > 0:
        tags.append("全线盈利")

    if tags:
        cur.execute("""
            UPDATE sim_runs SET tags = %s, is_notable = %s, label = %s
            WHERE sim_id = %s
        """, (tags, is_notable, "/".join(tags), sim_id))

    conn.commit()
    conn.close()

    print(f"  Tags: {tags if tags else '无'}")

    # 生成 Markdown 报告
    tag_str = ", ".join(tags) if tags else "无"
    notable_str = "⭐ 有代表意义" if is_notable else "普通"

    # 持仓汇总（最后一天）
    last_date = sim_dates[-1]
    last_positions = [p for p in all_positions if p["trade_date"] == last_date]

    pos_section = ""
    if last_positions:
        pos_section = "\n## 最终持仓明细\n\n"
        pos_section += "| 策略 | 股票 | 股数 | 成本 | 现价 | 市值 | 盈亏% | 持仓天数 |\n"
        pos_section += "|------|------|------|------|------|------|-------|----------|\n"
        for p in sorted(last_positions, key=lambda x: (x["strategy"], -x["market_value"])):
            pos_section += (f"| {p['strategy']} | {p['ts_code']} | {p['shares']} | "
                          f"{p['avg_cost']:.2f} | {p['market_price']:.2f} | "
                          f"{p['market_value']:,.0f} | {p['pnl_pct']:+.2f}% | {p['hold_days']} |\n")

    report = f"""# 模拟交易报告 {sim_id}

| 项目 | 值 |
|------|-----|
| 模拟编号 | {sim_id} |
| 时间窗口 | {start_date} ~ {end_date} |
| 持仓时长 | {months} 个月 ({days} 个交易日) |
| 市场环境 | BULL {regime_counts.get('BULL',0)}天 / NEUTRAL {regime_counts.get('NEUTRAL',0)}天 / CRISIS {regime_counts.get('CRISIS',0)}天 |
| 标签 | {tag_str} |
| 代表性 | {notable_str} |

## 策略表现

| 策略 | 收益% | 回撤% | Sharpe | 交易数 |
|------|-------|-------|--------|--------|
| Trend | {t_ret:+.2f} | {t_dd:.2f} | {t_sharpe:.2f} | {sum(1 for t in all_trades if t['strategy']=='Trend')} |
| LowVol | {l_ret:+.2f} | {l_dd:.2f} | {l_sharpe:.2f} | {sum(1 for t in all_trades if t['strategy']=='LowVol')} |
| Factor | {f_ret:+.2f} | {f_dd:.2f} | {f_sharpe:.2f} | {sum(1 for t in all_trades if t['strategy']=='Factor')} |
| **组合** | **{total_ret:+.2f}** | **{max_dd*100:.2f}** | **{total_sharpe:.2f}** | **{len(all_trades)}** |
{pos_section}
## 标注

- 标签: {tag_str}
- 代表性: {notable_str}
- 备注:

---
*Generated at {datetime.now().isoformat()}*
"""
    report_path = os.path.join(REPORT_DIR, f"{sim_id}.md")
    with open(report_path, "w") as f:
        f.write(report)

    # 输出摘要
    print(f"\n  Result: ret={total_ret:+.2f}% dd={max_dd*100:.2f}% sharpe={total_sharpe:.2f}")
    print(f"  Trend={t_ret:+.2f}% LowVol={l_ret:+.2f}% Factor={f_ret:+.2f}%")
    print(f"  Trades: {len(all_trades)}, Report: {report_path}")
    print(f"  PG: sim_runs + {len(daily_records)} daily + {len(all_trades)} trades")

    return sim_id


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo Strategy Sim")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (every 30min)")
    parser.add_argument("--count", type=int, default=1, help="Number of simulations")
    parser.add_argument("--interval", type=int, default=1800, help="Daemon interval (seconds)")
    parser.add_argument("--start", type=str, default=None, help="Fixed start date")
    parser.add_argument("--end", type=str, default=None, help="Fixed end date")
    parser.add_argument("--months", type=int, default=None, help="Fixed duration months")
    args = parser.parse_args()

    if args.daemon:
        print(f"[sim] Daemon mode, interval={args.interval}s")
        while True:
            try:
                run_single_sim(args.start, args.end, args.months)
            except Exception as e:
                print(f"[sim] Error: {e}")
            time.sleep(args.interval)
    else:
        for i in range(args.count):
            print(f"\n[sim] Run {i+1}/{args.count}")
            try:
                run_single_sim(args.start, args.end, args.months)
            except Exception as e:
                print(f"[sim] Error: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
