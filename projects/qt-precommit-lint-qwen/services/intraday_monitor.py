"""
盘中实时监控 — Phase 4
接入腾讯实时行情，跟踪三策略模拟盘持仓表现

功能:
1. 每 30 秒刷新持仓市值
2. 实时计算组合收益/回撤
3. 触发止损/止盈预警
4. 开盘/午盘/收盘三次推送飞书快照

用法:
    python services/intraday_monitor.py              # 单次快照
    python services/intraday_monitor.py --daemon      # 盘中持续监控
"""

import json
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.realtime_quotes import get_realtime_quotes

# ── 配置 ──
STATE_FILE = "logs/paper_trading_v2/state.json"
SNAPSHOT_DIR = "logs/intraday"
INITIAL_CAPITAL = 1_000_000
REFRESH_INTERVAL = 30  # 秒

# 预警阈值
ALERT_DRAWDOWN = 0.05  # 组合回撤 >5% 预警
ALERT_SINGLE_LOSS = -0.08  # 单只亏损 >8% 预警

os.makedirs(SNAPSHOT_DIR, exist_ok=True)


def load_paper_state():
    """加载模拟盘持仓状态"""
    if not os.path.exists(STATE_FILE):
        print("[monitor] No paper trading state found")
        return None
    with open(STATE_FILE) as f:
        return json.load(f)


def collect_all_positions(state):
    """从模拟盘状态中提取所有持仓"""
    positions = []
    for strat_name, acc in state.get("accounts", {}).items():
        for ts_code, pos in acc.get("positions", {}).items():
            positions.append(
                {
                    "strategy": strat_name,
                    "ts_code": ts_code,
                    "shares": pos.get("shares", 0),
                    "avg_cost": pos.get("avg_cost", 0),
                }
            )
    return positions


def compute_snapshot(positions, quotes, state):
    """计算实时快照"""
    now = datetime.now()
    strat_summary = {}

    alerts = []
    all_holdings = []

    for pos in positions:
        code = pos["ts_code"]
        strat = pos["strategy"]
        shares = pos["shares"]
        avg_cost = pos["avg_cost"]

        q = quotes.get(code)
        if not q or q["price"] <= 0:
            continue

        price = q["price"]
        mkt_val = price * shares
        cost_val = avg_cost * shares
        pnl = (price / avg_cost - 1) * 100 if avg_cost > 0 else 0

        holding = {
            "strategy": strat,
            "ts_code": code,
            "name": q.get("name", ""),
            "shares": shares,
            "avg_cost": round(avg_cost, 2),
            "price": price,
            "change_pct": q["change_pct"],
            "mkt_value": round(mkt_val, 2),
            "pnl_pct": round(pnl, 2),
        }
        all_holdings.append(holding)

        # 策略汇总
        if strat not in strat_summary:
            strat_summary[strat] = {"equity": 0, "positions": 0, "cost": 0}
        strat_summary[strat]["equity"] += mkt_val
        strat_summary[strat]["cost"] += cost_val
        strat_summary[strat]["positions"] += 1

        # 单只预警
        if pnl / 100 < ALERT_SINGLE_LOSS:
            alerts.append(f"⚠ {code}({q.get('name', '')}) 亏损 {pnl:.1f}%")

    # 加上各策略现金
    for strat_name, acc in state.get("accounts", {}).items():
        cash = acc.get("cash", 0)
        if strat_name not in strat_summary:
            strat_summary[strat_name] = {"equity": 0, "positions": 0, "cost": 0}
        strat_summary[strat_name]["equity"] += cash
        strat_summary[strat_name]["cash"] = cash

    # 组合总权益
    cash_reserve = INITIAL_CAPITAL * 0.20
    total_equity = sum(s["equity"] for s in strat_summary.values()) + cash_reserve

    # 回撤
    max_equity = max(state.get("max_equity", INITIAL_CAPITAL), total_equity)
    drawdown = (max_equity - total_equity) / max_equity if max_equity > 0 else 0

    if drawdown > ALERT_DRAWDOWN:
        alerts.append(f"🔴 组合回撤 {drawdown:.2%} 超过阈值 {ALERT_DRAWDOWN:.0%}")

    ret_pct = (total_equity / INITIAL_CAPITAL - 1) * 100

    snapshot = {
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_equity": round(total_equity, 2),
        "return_pct": round(ret_pct, 2),
        "drawdown_pct": round(drawdown * 100, 2),
        "strategies": {},
        "holdings": all_holdings,
        "alerts": alerts,
    }

    for name, s in strat_summary.items():
        cost = s.get("cost", 0)
        eq = s["equity"]
        strat_ret = (eq / (INITIAL_CAPITAL * {"Trend": 0.35, "LowVol": 0.20, "Factor": 0.25}.get(name, 0.25)) - 1) * 100
        snapshot["strategies"][name] = {
            "equity": round(eq, 2),
            "positions": s["positions"],
            "cash": round(s.get("cash", 0), 2),
            "return_pct": round(strat_ret, 2),
        }

    return snapshot


def format_snapshot(snap):
    """格式化为文本"""
    lines = []
    lines.append(f"📊 盘中快照 {snap['time']}")
    lines.append(f"总权益: {snap['total_equity']:,.0f} ({snap['return_pct']:+.2f}%)")
    lines.append(f"回撤: {snap['drawdown_pct']:.2f}%")
    lines.append("")

    for name, s in snap["strategies"].items():
        lines.append(
            f"  {name:8s} 权益={s['equity']:>10,.0f} ({s['return_pct']:+.2f}%) 持仓={s['positions']}只 现金={s['cash']:,.0f}"
        )

    # Top 持仓
    holdings = sorted(snap["holdings"], key=lambda x: abs(x["mkt_value"]), reverse=True)
    if holdings:
        lines.append(f"\nTop 持仓 ({len(holdings)}只):")
        for h in holdings[:10]:
            lines.append(
                f"  {h['ts_code']} {h['name']:6s} {h['strategy']:6s} "
                f"现价={h['price']:>8.2f} 今日={h['change_pct']:>+5.2f}% "
                f"盈亏={h['pnl_pct']:>+6.2f}% 市值={h['mkt_value']:>10,.0f}"
            )

    if snap["alerts"]:
        lines.append(f"\n预警:")
        for a in snap["alerts"]:
            lines.append(f"  {a}")

    return "\n".join(lines)


def save_snapshot(snap):
    """保存快照到文件"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H%M")
    path = os.path.join(SNAPSHOT_DIR, f"{date_str}_{time_str}.json")
    with open(path, "w") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    return path


def run_once():
    """单次快照"""
    state = load_paper_state()
    if not state:
        return None

    positions = collect_all_positions(state)
    if not positions:
        print("[monitor] No positions")
        return None

    # 获取所有持仓的实时行情
    codes = list(set(p["ts_code"] for p in positions))
    print(f"[monitor] Fetching quotes for {len(codes)} stocks...")
    quotes = get_realtime_quotes(codes)
    print(f"[monitor] Got {len(quotes)} quotes")

    snap = compute_snapshot(positions, quotes, state)
    text = format_snapshot(snap)
    print(text)

    path = save_snapshot(snap)
    print(f"\nSaved: {path}")

    return snap


def run_daemon(interval=REFRESH_INTERVAL):
    """盘中持续监控"""
    print(f"[monitor] Daemon mode, interval={interval}s")
    print(f"[monitor] Trading hours: 9:30-11:30, 13:00-15:00")

    while True:
        now = datetime.now()
        hour, minute = now.hour, now.minute
        t = hour * 100 + minute

        # 交易时间: 9:25-11:35, 12:55-15:05 (留余量)
        is_trading = (925 <= t <= 1135) or (1255 <= t <= 1505)

        if is_trading:
            try:
                snap = run_once()
                if snap and snap.get("alerts"):
                    print(f"\n[ALERT] {len(snap['alerts'])} alerts!")
            except Exception as e:
                print(f"[monitor] Error: {e}")
        else:
            # 非交易时间，每 5 分钟检查一次
            if t < 925:
                wait = max(60, (925 - t) * 60 // 100)
                print(f"[monitor] Pre-market, next check in {wait}s")
                time.sleep(min(wait, 300))
                continue
            elif t > 1505:
                print(f"[monitor] Market closed. Exiting.")
                break
            else:
                # 午休
                print(f"[monitor] Lunch break, waiting...")
                time.sleep(300)
                continue

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Intraday Monitor")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon during trading hours")
    parser.add_argument("--interval", type=int, default=REFRESH_INTERVAL, help="Refresh interval (seconds)")
    args = parser.parse_args()

    if args.daemon:
        run_daemon(args.interval)
    else:
        run_once()


if __name__ == "__main__":
    main()
