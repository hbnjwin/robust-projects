"""
模拟盘引擎 v1 (Paper Trading Engine)

每日收盘后运行：
1. 读取当日信号（signal_generator 输出）
2. 用当日真实行情模拟执行
3. 更新模拟持仓和权益
4. 记录模拟交易日志
5. 输出每日模拟盘快照

状态持久化到 JSON 文件，进程重启后可恢复。
"""

import json
import os
from datetime import datetime, timedelta

from live.data_loader import load_market_data
from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine

STATE_FILE = "logs/paper_trading/state.json"
TRADE_LOG_DIR = "logs/paper_trading/trades"
SNAPSHOT_DIR = "logs/paper_trading/snapshots"
SIGNAL_DIR = "logs/signals"

os.makedirs("logs/paper_trading", exist_ok=True)
os.makedirs(TRADE_LOG_DIR, exist_ok=True)
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

INITIAL_CAPITAL = 1_000_000


def load_state():
    """从文件恢复模拟盘状态"""
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    """持久化模拟盘状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4, default=str)


def init_state():
    """初始化模拟盘"""
    return {
        "start_date": str(datetime.now().date()),
        "cash": INITIAL_CAPITAL,
        "positions": {},
        "total_equity": INITIAL_CAPITAL,
        "max_equity": INITIAL_CAPITAL,
        "max_drawdown": 0,
        "trade_count": 0,
        "day_count": 0,
        "equity_curve": [],
    }


def run_paper_trading():
    today = datetime.now().date()
    today_str = str(today)

    # 1. 加载或初始化状态
    state = load_state()
    if state is None:
        state = init_state()
        print(f"📋 Paper trading initialized with {INITIAL_CAPITAL:,.0f} capital")

    # 2. 读取今日信号
    signal_file = os.path.join(SIGNAL_DIR, f"{today_str}.json")
    if not os.path.exists(signal_file):
        print(f"⚠ No signal file for {today_str}, skipping.")
        return

    with open(signal_file, "r") as f:
        signals = json.load(f)

    # 3. 获取今日行情
    yesterday = (today - timedelta(days=7)).strftime("%Y-%m-%d")  # 足够回溯
    market_data = load_market_data(yesterday, today_str)

    if today_str not in market_data:
        print(f"⚠ No market data for {today_str}, skipping.")
        return

    prices = market_data[today_str]

    # 4. 构建模拟账户（从持久化状态恢复）
    account = StrategyAccount("PaperTrading", INITIAL_CAPITAL)
    account.cash = state["cash"]
    for code, pos in state["positions"].items():
        account.positions[code] = {"shares": pos["shares"], "avg_cost": pos.get("avg_cost", 0)}

    engine = ExecutionEngine(account)

    # 5. 执行信号
    all_signals = signals.get("trend_signals", []) + signals.get("lowvol_signals", [])

    if all_signals:
        engine.queue_orders(all_signals)
        engine.execute(prices, date=today_str)

    # 6. 估值
    account.mark_to_market(prices)

    # 7. 更新状态
    equity = account.total_equity
    if equity > state["max_equity"]:
        state["max_equity"] = equity
    dd = (state["max_equity"] - equity) / state["max_equity"] if state["max_equity"] > 0 else 0
    state["max_drawdown"] = max(state["max_drawdown"], dd)

    state["cash"] = account.cash
    state["positions"] = {}
    for code, pos in account.positions.items():
        state["positions"][code] = {"shares": pos["shares"], "avg_cost": pos.get("avg_cost", 0)}
    state["total_equity"] = equity
    state["trade_count"] += len(account.trade_log)
    state["day_count"] += 1
    state["equity_curve"].append({"date": today_str, "equity": equity, "drawdown": dd})

    # 8. 保存状态
    save_state(state)

    # 9. 保存今日交易日志
    if account.trade_log:
        trade_path = os.path.join(TRADE_LOG_DIR, f"{today_str}.json")
        with open(trade_path, "w") as f:
            json.dump(account.trade_log, f, indent=4, default=str)

    # 10. 保存今日快照
    snapshot = {
        "date": today_str,
        "regime": signals.get("regime", "UNKNOWN"),
        "equity": equity,
        "cash": account.cash,
        "positions_count": len(account.positions),
        "drawdown": dd,
        "max_drawdown": state["max_drawdown"],
        "trades_today": len(account.trade_log),
        "signals_count": len(all_signals),
    }
    snap_path = os.path.join(SNAPSHOT_DIR, f"{today_str}.json")
    with open(snap_path, "w") as f:
        json.dump(snapshot, f, indent=4)

    # 11. 输出摘要
    print(f"✅ Paper trading day {state['day_count']}: {today_str}")
    print(f"   Equity: {equity:,.2f}")
    print(f"   Cash: {account.cash:,.2f}")
    print(f"   Positions: {len(account.positions)}")
    print(f"   Trades today: {len(account.trade_log)}")
    print(f"   Max Drawdown: {state['max_drawdown']:.2%}")
    print(f"   Regime: {signals.get('regime', 'UNKNOWN')}")


if __name__ == "__main__":
    run_paper_trading()
