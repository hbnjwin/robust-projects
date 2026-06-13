"""
模拟盘引擎 v2 (Paper Trading Engine)

三策略联合执行: Trend + LowVol + ML-Factor
读取 ML 信号格式，用 data_loader_fast 加载行情

每日收盘后运行 (15:25):
1. 读取 ML 信号 (data/signals/YYYY-MM-DD.json)
2. 回放近期行情建立 Trend/LowVol 策略状态
3. 用当日真实行情模拟执行三策略
4. 更新模拟持仓和权益
5. 输出每日快照 + 飞书/邮件通知

状态持久化到 JSON，进程重启后可恢复。
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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

STATE_DIR = "logs/paper_trading_v2"
STATE_FILE = os.path.join(STATE_DIR, "state.json")
TRADE_LOG_DIR = os.path.join(STATE_DIR, "trades")
SNAPSHOT_DIR = os.path.join(STATE_DIR, "snapshots")
ML_SIGNAL_DIR = "data/signals"
LOOKBACK_DAYS = 120  # 策略预热天数

os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(TRADE_LOG_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def init_state():
    return {
        "start_date": str(datetime.now().date()),
        "initial_capital": INITIAL_CAPITAL,
        "accounts": {
            "Trend": {"cash": INITIAL_CAPITAL * TREND_RATIO, "positions": {}},
            "LowVol": {"cash": INITIAL_CAPITAL * LOWVOL_RATIO, "positions": {}},
            "Factor": {"cash": INITIAL_CAPITAL * FACTOR_RATIO, "positions": {}},
        },
        "total_equity": INITIAL_CAPITAL,
        "max_equity": INITIAL_CAPITAL,
        "max_drawdown": 0,
        "day_count": 0,
        "equity_curve": [],
    }


def restore_account(name, state_data):
    """从持久化状态恢复 StrategyAccount"""
    acc_state = state_data["accounts"].get(name, {})
    capital = {
        "Trend": INITIAL_CAPITAL * TREND_RATIO,
        "LowVol": INITIAL_CAPITAL * LOWVOL_RATIO,
        "Factor": INITIAL_CAPITAL * FACTOR_RATIO,
    }[name]

    account = StrategyAccount(name, capital)
    account.cash = acc_state.get("cash", capital)
    for code, pos in acc_state.get("positions", {}).items():
        account.positions[code] = {
            "shares": pos["shares"],
            "avg_cost": pos.get("avg_cost", 0),
            "buy_date": pos.get("buy_date"),
        }
    return account


def serialize_account(account):
    """序列化 StrategyAccount 到 dict"""
    positions = {}
    for code, pos in account.positions.items():
        positions[code] = {
            "shares": pos["shares"],
            "avg_cost": pos.get("avg_cost", 0),
            "buy_date": str(pos.get("buy_date", "")),
        }
    return {"cash": account.cash, "positions": positions}


def load_ml_signal(date_str):
    """加载当日 ML 信号"""
    path = os.path.join(ML_SIGNAL_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def run_paper_trading():
    today = datetime.now().date()
    today_str = str(today)

    print(f"{'='*60}")
    print(f"  Paper Trading V2 — {today_str}")
    print(f"{'='*60}")

    # 1. 加载或初始化状态
    state = load_state()
    if state is None:
        state = init_state()
        print(f"  Initialized with {INITIAL_CAPITAL:,.0f} capital")
        print(f"  Trend={TREND_RATIO:.0%} LowVol={LOWVOL_RATIO:.0%} Factor={FACTOR_RATIO:.0%} Cash={CASH_RATIO:.0%}")

    # 2. 加载行情（最近 LOOKBACK_DAYS 天，用于策略预热）
    start = (today - timedelta(days=LOOKBACK_DAYS + 30)).strftime("%Y-%m-%d")
    print(f"\n  Loading market data {start} ~ {today_str}...")
    market_data = load_market_data_fast(start, today_str)

    if not market_data:
        print("  [ERROR] No market data available")
        return

    dates = sorted(market_data.keys())
    if today_str not in market_data:
        # 找最近的交易日
        latest = dates[-1] if dates else None
        if latest:
            days_gap = (today - datetime.strptime(latest, "%Y-%m-%d").date()).days
            if days_gap > 5:
                print(f"  [ERROR] Data too old: latest={latest}, gap={days_gap} days")
                return
            today_str = latest
            print(f"  Using latest trading day: {today_str}")
        else:
            print("  [ERROR] No trading days found")
            return

    print(f"  Market data: {len(dates)} days, latest: {dates[-1]}")

    # 3. 加载 ML 信号
    ml_signal = load_ml_signal(today_str)
    ml_scores = {}
    regime_from_signal = "NEUTRAL"
    if ml_signal:
        ml_scores = ml_signal.get("all_signals", {})
        regime_from_signal = ml_signal.get("regime", "NEUTRAL")
        print(f"  ML signal: {len(ml_scores)} stocks, regime={regime_from_signal}")
    else:
        print(f"  [WARN] No ML signal for {today_str}")

    # 4. 恢复账户
    trend_acc = restore_account("Trend", state)
    lowvol_acc = restore_account("LowVol", state)
    factor_acc = restore_account("Factor", state)

    trend_eng = ExecutionEngine(trend_acc)
    lowvol_eng = ExecutionEngine(lowvol_acc)
    factor_eng = ExecutionEngine(factor_acc)

    # 5. 策略预热：回放历史数据建立状态
    trend = TrendStrategyV2()
    lowvol = LowVolStrategy()
    regime_detector = RegimeDetectorV2()

    # Factor 策略：优先用组合优化器权重，fallback 到等权 top-N
    portfolio_weights = {}
    portfolio_path = os.path.join("data/portfolio", f"{today_str}.json")
    if os.path.exists(portfolio_path):
        with open(portfolio_path) as f:
            portfolio_weights = json.load(f).get("weights", {})
        print(f"  Portfolio optimizer: {len(portfolio_weights)} stocks (optimized weights)")
    else:
        print(f"  [INFO] No portfolio file for {today_str}, using equal-weight top-N")

    factor_signals_map = {today_str: ml_scores} if ml_scores else {}
    factor_strat = FactorStrategy(factor_scores=factor_signals_map, top_n=15, rebalance_days=5)

    print(f"  Warming up strategies ({len(dates)} days)...")
    for date in dates:
        prices = market_data[date]

        # Regime 检测
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            regime_detector.update(np.mean(closes), 0)
        regime = regime_detector.detect()

        if date == today_str:
            # 今天：真正执行
            break

        # 预热：只更新策略状态，不执行交易
        trend.generate(date, prices)
        lowvol.generate(date, prices)

    # 6. 今日执行
    prices = market_data[today_str]
    # 优先使用 ML 信号文件中的 regime，RegimeDetectorV2 作为兜底
    regime = regime_from_signal if regime_from_signal != "NEUTRAL" else regime_detector.detect()
    if regime_from_signal != "NEUTRAL":
        print(f"\n  Today: {today_str}, Regime: {regime} (from ML signal)")
    else:
        regime = regime_detector.detect()
        print(f"\n  Today: {today_str}, Regime: {regime} (from RegimeDetectorV2)")

    # Trend 信号
    trend_signals = trend.generate(today_str, prices)
    # LowVol 信号
    lowvol.set_regime(regime)
    lowvol_signals = lowvol.generate(today_str, prices)
    # Factor 信号 (ML) — 优先用组合优化器权重
    if portfolio_weights:
        # 用优化器权重生成信号
        current_holdings = set(factor_acc.positions.keys())
        target_holdings = set(portfolio_weights.keys())
        factor_signals = []
        # 卖出不在目标中的
        for code in current_holdings - target_holdings:
            factor_signals.append({"action": "sell", "ts_code": code})
        # 买入/调仓
        for code, weight in portfolio_weights.items():
            if code not in current_holdings:
                factor_signals.append({"action": "buy", "ts_code": code, "weight": weight})
    else:
        factor_signals = factor_strat.generate(today_str, prices)

    # Crisis: 清仓
    if regime == "CRISIS":
        print("  ⚠ CRISIS detected — liquidating all positions")
        trend_signals = [{"action": "sell", "ts_code": c} for c in list(trend_acc.positions.keys())]
        lowvol_signals = [{"action": "sell", "ts_code": c} for c in list(lowvol_acc.positions.keys())]
        factor_signals = [{"action": "sell", "ts_code": c} for c in list(factor_acc.positions.keys())]

    # 执行
    trend_eng.queue_orders(trend_signals)
    lowvol_eng.queue_orders(lowvol_signals)
    factor_eng.queue_orders(factor_signals)

    trend_eng.execute(prices, date=today_str)
    lowvol_eng.execute(prices, date=today_str)
    factor_eng.execute(prices, date=today_str)

    # 7. 估值
    trend_acc.mark_to_market(prices)
    lowvol_acc.mark_to_market(prices)
    factor_acc.mark_to_market(prices)

    total_equity = (
        trend_acc.total_equity
        + lowvol_acc.total_equity
        + factor_acc.total_equity
        + INITIAL_CAPITAL * CASH_RATIO  # 现金储备不动
    )

    # 8. 更新状态
    if total_equity > state["max_equity"]:
        state["max_equity"] = total_equity
    dd = (state["max_equity"] - total_equity) / state["max_equity"] if state["max_equity"] > 0 else 0
    state["max_drawdown"] = max(state["max_drawdown"], dd)

    state["accounts"]["Trend"] = serialize_account(trend_acc)
    state["accounts"]["LowVol"] = serialize_account(lowvol_acc)
    state["accounts"]["Factor"] = serialize_account(factor_acc)
    state["total_equity"] = total_equity
    state["day_count"] += 1
    state["equity_curve"].append({
        "date": today_str,
        "equity": round(total_equity, 2),
        "drawdown": round(dd, 4),
    })

    save_state(state)

    # 9. 交易日志
    all_trades = trend_acc.trade_log + lowvol_acc.trade_log + factor_acc.trade_log
    if all_trades:
        trade_path = os.path.join(TRADE_LOG_DIR, f"{today_str}.json")
        with open(trade_path, "w") as f:
            json.dump(all_trades, f, indent=2, default=str)

    # 10. 快照
    snapshot = {
        "date": today_str,
        "regime": regime,
        "total_equity": round(total_equity, 2),
        "return_pct": round((total_equity / INITIAL_CAPITAL - 1) * 100, 2),
        "max_drawdown_pct": round(state["max_drawdown"] * 100, 2),
        "accounts": {
            "Trend": {
                "equity": round(trend_acc.total_equity, 2),
                "positions": len(trend_acc.positions),
                "trades": len(trend_acc.trade_log),
            },
            "LowVol": {
                "equity": round(lowvol_acc.total_equity, 2),
                "positions": len(lowvol_acc.positions),
                "trades": len(lowvol_acc.trade_log),
            },
            "Factor": {
                "equity": round(factor_acc.total_equity, 2),
                "positions": len(factor_acc.positions),
                "trades": len(factor_acc.trade_log),
            },
        },
        "ml_signal_count": len(ml_scores),
        "day_count": state["day_count"],
    }

    snap_path = os.path.join(SNAPSHOT_DIR, f"{today_str}.json")
    with open(snap_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    # 11. 输出摘要
    ret_pct = (total_equity / INITIAL_CAPITAL - 1) * 100
    print(f"\n  {'─'*50}")
    print(f"  Day {state['day_count']} Summary:")
    print(f"  Total Equity:  {total_equity:>12,.2f} ({ret_pct:+.2f}%)")
    print(f"  Max Drawdown:  {state['max_drawdown']:>12.2%}")
    print(f"  Regime:        {regime}")
    print(f"  ┌─────────────┬────────────┬──────┬────────┐")
    print(f"  │ Strategy    │    Equity  │ Pos  │ Trades │")
    print(f"  ├─────────────┼────────────┼──────┼────────┤")
    for name, acc in [("Trend", trend_acc), ("LowVol", lowvol_acc), ("Factor", factor_acc)]:
        print(f"  │ {name:<11} │ {acc.total_equity:>10,.0f} │ {len(acc.positions):>4} │ {len(acc.trade_log):>6} │")
    print(f"  └─────────────┴────────────┴──────┴────────┘")
    print(f"  Snapshot: {snap_path}")
    print(f"{'='*60}")

    return snapshot


if __name__ == "__main__":
    run_paper_trading()
