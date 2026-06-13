"""
Paper Runner - vnpy 模拟盘主入口

每日收盘后由 OpenClaw Cron 调度运行：
1. 初始化 vnpy MainEngine + PgDailyGateway + PaperEngine
2. 读取今日信号
3. 推送今日行情
4. 执行订单（PaperEngine 模拟撮合）
5. 输出持仓快照、交易流水、PnL 报告
6. 同步 watchlist.in_position 状态
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from copy import copy

# 确保 quant 目录在 path 中
QUANT_DIR = Path(__file__).resolve().parents[1]
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import psycopg
from vnpy.event import Event, EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_TRADE, EVENT_ORDER, EVENT_LOG
from vnpy.trader.object import TradeData, OrderData, LogData
from vnpy.trader.constant import Direction, Status

from vnpy_ext.pg_daily_gateway import PgDailyGateway, parse_ts_code, to_ts_code
from vnpy_ext.signal_bridge import SignalBridge
from vnpy_paperaccount.engine import PaperEngine

from config import PG_CONFIG

# 目录
LOG_DIR = QUANT_DIR / "logs" / "vnpy_paper"
SNAPSHOT_DIR = LOG_DIR / "snapshots"
TRADE_LOG_DIR = LOG_DIR / "trades"
SIGNAL_DIR = QUANT_DIR / "logs" / "signals"

for d in [LOG_DIR, SNAPSHOT_DIR, TRADE_LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 1_000_000.0


class PaperRunner:
    """vnpy 模拟盘运行器"""

    def __init__(self, capital: float = INITIAL_CAPITAL):
        self.capital = capital
        self.trades: list[dict] = []
        self.orders: list[dict] = []

        # 初始化 vnpy 引擎
        self.event_engine = EventEngine()
        self.main_engine = MainEngine(self.event_engine)

        # 加载 PgDailyGateway
        self.gateway = self.main_engine.add_gateway(PgDailyGateway)

        # 加载 PaperEngine（会 monkey-patch MainEngine 的 send_order 等方法）
        self.paper_engine = self.main_engine.add_engine(PaperEngine)
        self.paper_engine.set_instant_trade(True)  # 即时撮合

        # 信号桥接
        self.bridge = SignalBridge(total_capital=capital)

        # 注册事件回调
        self.event_engine.register(EVENT_TRADE, self._on_trade)
        self.event_engine.register(EVENT_ORDER, self._on_order)
        self.event_engine.register(EVENT_LOG, self._on_log)

    def _on_trade(self, event: Event) -> None:
        """成交回调"""
        trade: TradeData = event.data
        record = {
            "tradeid": trade.tradeid,
            "symbol": trade.symbol,
            "exchange": trade.exchange.value,
            "ts_code": to_ts_code(trade.symbol, trade.exchange),
            "direction": trade.direction.value,
            "offset": trade.offset.value,
            "price": trade.price,
            "volume": trade.volume,
            "datetime": str(trade.datetime) if trade.datetime else "",
        }
        self.trades.append(record)
        print(f"  ✅ 成交: {record['ts_code']} {record['direction']} {record['volume']}股 @ {record['price']}")

    def _on_order(self, event: Event) -> None:
        """委托回调"""
        order: OrderData = event.data
        record = {
            "orderid": order.orderid,
            "symbol": order.symbol,
            "exchange": order.exchange.value,
            "direction": order.direction.value if order.direction else "",
            "status": order.status.value,
            "price": order.price,
            "volume": order.volume,
            "traded": order.traded,
        }
        self.orders.append(record)

    def _on_log(self, event: Event) -> None:
        """日志回调"""
        log: LogData = event.data
        print(f"  [LOG] {log.gateway_name}: {log.msg}")

    def connect(self) -> None:
        """连接 Gateway"""
        self.main_engine.connect(PgDailyGateway.default_setting, "PG_DAILY")
        # 等待合约加载完成
        time.sleep(0.5)

    def get_current_positions(self) -> dict[str, float]:
        """从 PaperEngine 获取当前持仓 {ts_code: volume}"""
        positions: dict[str, float] = {}
        for pos in self.main_engine.get_all_positions():
            if pos.volume > 0:
                ts_code = to_ts_code(pos.symbol, pos.exchange)
                if pos.direction == Direction.LONG or pos.direction == Direction.NET:
                    positions[ts_code] = pos.volume
        return positions

    def run_date(self, trade_date: str) -> dict:
        """
        运行指定日期的模拟盘。

        Args:
            trade_date: 'YYYY-MM-DD'

        Returns:
            当日快照 dict
        """
        print(f"\n{'=' * 60}")
        print(f"📊 vnpy Paper Trading: {trade_date}")
        print(f"{'=' * 60}")

        self.trades.clear()
        self.orders.clear()

        # 1. 推送当日行情
        ticks = self.gateway.replay_date(trade_date)
        if not ticks:
            print(f"⚠ 无 {trade_date} 行情数据，跳过")
            return {}

        # 等待事件处理
        time.sleep(0.3)

        # 2. 获取当前价格和持仓
        current_prices = {ts_code: tick.last_price for ts_code, tick in ticks.items()}
        current_positions = self.get_current_positions()

        print(f"  当前持仓: {len(current_positions)} 只")
        for ts_code, vol in list(current_positions.items())[:5]:
            price = current_prices.get(ts_code, 0)
            print(f"    {ts_code}: {vol:.0f}股 @ {price:.2f}")
        if len(current_positions) > 5:
            print(f"    ... 共 {len(current_positions)} 只")

        # 3. 加载并转换信号
        order_requests = self.bridge.load_and_convert(
            signal_date=trade_date,
            signal_dir=str(SIGNAL_DIR),
            current_prices=current_prices,
            current_positions=current_positions,
        )

        print(f"  信号转换: {len(order_requests)} 笔委托")

        # 4. 发送委托（PaperEngine 即时撮合）
        for req in order_requests:
            vt_orderid = self.main_engine.send_order(req, "PG_DAILY")
            if vt_orderid:
                print(
                    f"  📤 委托: {req.symbol}.{req.exchange.value} "
                    f"{req.direction.value} {req.volume:.0f}股 @ {req.price:.2f}"
                )

        # 等待撮合完成
        time.sleep(0.5)

        # 5. 计算持仓和权益
        final_positions = self.get_current_positions()
        total_position_value = 0.0
        position_details = []

        for ts_code, vol in final_positions.items():
            price = current_prices.get(ts_code, 0)
            value = vol * price
            total_position_value += value
            position_details.append(
                {
                    "ts_code": ts_code,
                    "volume": vol,
                    "price": price,
                    "value": value,
                }
            )

        # 估算现金（简化：总资金 - 持仓市值）
        # 实际应从 PaperEngine 的 AccountData 获取
        accounts = self.main_engine.get_all_accounts()
        cash = accounts[0].available if accounts else self.capital - total_position_value
        total_equity = cash + total_position_value

        # 6. 构建快照
        snapshot = {
            "date": trade_date,
            "total_equity": round(total_equity, 2),
            "cash": round(cash, 2),
            "position_value": round(total_position_value, 2),
            "positions_count": len(final_positions),
            "trades_today": len(self.trades),
            "orders_today": len([o for o in self.orders if o["status"] != Status.REJECTED.value]),
            "positions": position_details,
        }

        # 7. 保存快照和交易日志
        snap_path = SNAPSHOT_DIR / f"{trade_date}.json"
        with open(snap_path, "w") as f:
            json.dump(snapshot, f, indent=4, default=str, ensure_ascii=False)

        if self.trades:
            trade_path = TRADE_LOG_DIR / f"{trade_date}.json"
            with open(trade_path, "w") as f:
                json.dump(self.trades, f, indent=4, default=str, ensure_ascii=False)

        # 8. 同步 watchlist.in_position
        self._sync_watchlist_positions(final_positions)

        # 9. 输出摘要
        print(f"\n  📋 日终快照:")
        print(f"     总权益: {total_equity:,.2f}")
        print(f"     现金:   {cash:,.2f}")
        print(f"     持仓:   {len(final_positions)} 只, 市值 {total_position_value:,.2f}")
        print(f"     成交:   {len(self.trades)} 笔")
        print(f"{'=' * 60}\n")

        return snapshot

    def _sync_watchlist_positions(self, positions: dict[str, float]) -> None:
        """同步持仓状态到 watchlist.in_position"""
        try:
            conn = psycopg.connect(**PG_CONFIG)
            cur = conn.cursor()

            # 先全部置 false
            cur.execute("UPDATE watchlist SET in_position = FALSE")

            # 持仓中的置 true
            if positions:
                ts_codes = list(positions.keys())
                placeholders = ",".join(["%s"] * len(ts_codes))
                cur.execute(
                    f"UPDATE watchlist SET in_position = TRUE WHERE ts_code IN ({placeholders})",
                    ts_codes,
                )

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"  ⚠ watchlist 同步失败: {e}")

    def close(self) -> None:
        """关闭引擎"""
        self.main_engine.close()


def run_today():
    """运行今日模拟盘"""
    today = datetime.now().date()

    # 查找最近的交易日（daily_price 中有数据的最新日期）
    conn = psycopg.connect(**PG_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT MAX(trade_date) FROM daily_price WHERE trade_date <= %s", (today,))
    result = cur.fetchone()
    conn.close()

    if not result or not result[0]:
        print("❌ 无可用交易日数据")
        return

    trade_date = str(result[0])
    print(f"📅 最近交易日: {trade_date}")

    runner = PaperRunner(capital=INITIAL_CAPITAL)
    try:
        runner.connect()
        snapshot = runner.run_date(trade_date)
        if snapshot:
            print(f"✅ 模拟盘完成: {trade_date}")
            print(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str))
    finally:
        runner.close()


if __name__ == "__main__":
    run_today()
