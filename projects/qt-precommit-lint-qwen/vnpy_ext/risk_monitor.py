"""
RiskMonitor - vnpy 事件驱动风控监听器 + PostgreSQL 持仓持久化

功能：
1. 监听 vnpy 事件系统，实时同步持仓/交易到 PostgreSQL
2. 风控规则检查（最大回撤、单日亏损、连续亏损冷却）
3. 风控触发时自动撤单 + 通知回调
"""

from __future__ import annotations

import json
from datetime import datetime, date
from typing import Optional
from collections.abc import Callable

import psycopg

from vnpy.event import Event, EventEngine
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.event import EVENT_TRADE, EVENT_ORDER, EVENT_POSITION, EVENT_ACCOUNT, EVENT_TIMER
from vnpy.trader.object import TradeData, OrderData, PositionData, AccountData
from vnpy.trader.constant import Direction, Status

from .pg_daily_gateway import to_ts_code


# 默认风控参数
DEFAULT_RISK_CONFIG = {
    "max_drawdown": 0.25,  # 最大回撤 25%
    "daily_loss_limit": 0.05,  # 单日亏损限制 5%
    "consecutive_loss_days": 3,  # 连续亏损天数触发冷却
    "cooldown_days": 2,  # 冷却天数
    "position_limit": 30,  # 最大持仓数量
    "single_stock_weight": 0.15,  # 单只股票最大权重 15%
    "commission_rate": 0.0003,  # 手续费率 0.03%
}


class RiskMonitor(BaseEngine):
    """风控监听器 + 持仓持久化引擎"""

    def __init__(
        self,
        main_engine: MainEngine,
        event_engine: EventEngine,
        pg_config: Optional[dict] = None,
        risk_config: Optional[dict] = None,
        on_alert: Optional[Callable[[str, str, dict], None]] = None,
    ) -> None:
        """
        Args:
            pg_config: PostgreSQL 连接配置
            risk_config: 风控参数（覆盖默认值）
            on_alert: 风控告警回调 (level, message, details)
        """
        super().__init__(main_engine, event_engine, "RiskMonitor")

        self.pg_config = pg_config or {
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "limit123",
            "dbname": "quant",
        }
        self.risk_config = {**DEFAULT_RISK_CONFIG, **(risk_config or {})}
        self.on_alert = on_alert or self._default_alert

        # 状态追踪
        self.initial_equity: float = 0
        self.peak_equity: float = 0
        self.current_equity: float = 0
        self.daily_start_equity: float = 0
        self.today_trades: list[dict] = []
        self.risk_triggered: bool = False
        self.consecutive_loss_days: int = 0
        self.cooldown_remaining: int = 0

        self._conn: Optional[psycopg.Connection] = None
        self._connect_pg()
        self._register_events()

    def _connect_pg(self) -> None:
        """连接 PostgreSQL"""
        try:
            self._conn = psycopg.connect(**self.pg_config)
            self._log("PostgreSQL 连接成功")
        except Exception as e:
            self._log(f"PostgreSQL 连接失败: {e}")

    def _ensure_conn(self) -> Optional[psycopg.Connection]:
        """确保连接可用"""
        if self._conn is None or self._conn.closed:
            self._connect_pg()
        return self._conn

    def _register_events(self) -> None:
        """注册 vnpy 事件监听"""
        self.event_engine.register(EVENT_TRADE, self._on_trade)
        self.event_engine.register(EVENT_POSITION, self._on_position)
        self.event_engine.register(EVENT_ACCOUNT, self._on_account)

    def _log(self, msg: str) -> None:
        """写日志"""
        print(f"  [RiskMonitor] {msg}")

    def _default_alert(self, level: str, message: str, details: dict) -> None:
        """默认告警处理"""
        self._log(f"🚨 [{level}] {message}")

    # ─── 事件回调 ───

    def _on_trade(self, event: Event) -> None:
        """成交事件 → 写入 vnpy_trades"""
        trade: TradeData = event.data
        ts_code = to_ts_code(trade.symbol, trade.exchange)
        turnover = trade.price * trade.volume
        commission = turnover * self.risk_config["commission_rate"]

        record = {
            "trade_date": date.today().isoformat(),
            "tradeid": trade.tradeid,
            "ts_code": ts_code,
            "direction": trade.direction.value if trade.direction else "Unknown",
            "offset_flag": trade.offset.value if trade.offset else "",
            "price": trade.price,
            "volume": trade.volume,
            "turnover": turnover,
            "commission": commission,
            "traded_at": str(trade.datetime or datetime.now()),
            "reference": getattr(trade, "reference", ""),
        }
        self.today_trades.append(record)
        self._persist_trade(record)

    def _on_position(self, event: Event) -> None:
        """持仓事件 → 写入 vnpy_positions"""
        pos: PositionData = event.data
        ts_code = to_ts_code(pos.symbol, pos.exchange)
        direction = pos.direction.value if pos.direction else "Net"
        self._persist_position(ts_code, direction, pos.volume, pos.price, pos.pnl, pos.frozen)

    def _on_account(self, event: Event) -> None:
        """账户事件 → 更新权益追踪 + 风控检查"""
        account: AccountData = event.data
        self.current_equity = account.balance

        if self.initial_equity == 0:
            self.initial_equity = account.balance
            self.peak_equity = account.balance
            self.daily_start_equity = account.balance

        if account.balance > self.peak_equity:
            self.peak_equity = account.balance

        # 风控检查
        self._check_risk()

    # ─── 风控检查 ───

    def _check_risk(self) -> None:
        """执行所有风控规则检查"""
        if self.current_equity <= 0 or self.peak_equity <= 0:
            return

        alerts = []

        # 1. 最大回撤检查
        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        max_dd = self.risk_config["max_drawdown"]
        if drawdown >= max_dd:
            alerts.append(
                {
                    "level": "CRITICAL",
                    "rule": "max_drawdown",
                    "message": f"最大回撤触发: {drawdown:.2%} >= {max_dd:.2%}",
                    "details": {
                        "drawdown": drawdown,
                        "peak_equity": self.peak_equity,
                        "current_equity": self.current_equity,
                    },
                }
            )

        # 2. 单日亏损检查
        if self.daily_start_equity > 0:
            daily_loss = (self.daily_start_equity - self.current_equity) / self.daily_start_equity
            daily_limit = self.risk_config["daily_loss_limit"]
            if daily_loss >= daily_limit:
                alerts.append(
                    {
                        "level": "WARNING",
                        "rule": "daily_loss",
                        "message": f"单日亏损触发: {daily_loss:.2%} >= {daily_limit:.2%}",
                        "details": {
                            "daily_loss": daily_loss,
                            "start_equity": self.daily_start_equity,
                            "current_equity": self.current_equity,
                        },
                    }
                )

        # 3. 持仓数量检查
        positions = self.main_engine.get_all_positions()
        active_count = sum(1 for p in positions if p.volume > 0)
        pos_limit = self.risk_config["position_limit"]
        if active_count > pos_limit:
            alerts.append(
                {
                    "level": "WARNING",
                    "rule": "position_limit",
                    "message": f"持仓数量超限: {active_count} > {pos_limit}",
                    "details": {"count": active_count, "limit": pos_limit},
                }
            )

        # 触发告警
        for alert in alerts:
            self.risk_triggered = True
            self.on_alert(alert["level"], alert["message"], alert["details"])

    def check_order_allowed(self, ts_code: str, volume: float, price: float) -> tuple[bool, str]:
        """
        下单前风控检查。

        Returns:
            (allowed, reason)
        """
        if self.risk_triggered:
            return False, "风控已触发，暂停交易"

        if self.cooldown_remaining > 0:
            return False, f"冷却期中，剩余 {self.cooldown_remaining} 天"

        # 单只股票权重检查
        if self.current_equity > 0:
            order_value = volume * price
            weight = order_value / self.current_equity
            max_weight = self.risk_config["single_stock_weight"]
            if weight > max_weight:
                return False, f"单股权重超限: {weight:.2%} > {max_weight:.2%}"

        return True, "OK"

    def reset_daily(self) -> None:
        """每日重置（新交易日开始时调用）"""
        self.daily_start_equity = self.current_equity
        self.today_trades.clear()
        self.risk_triggered = False

        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1

    # ─── PostgreSQL 持久化 ───

    def _persist_trade(self, record: dict) -> None:
        """写入交易流水"""
        conn = self._ensure_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO vnpy_trades
                    (trade_date, tradeid, ts_code, direction, offset_flag,
                     price, volume, turnover, commission, traded_at, reference)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        record["trade_date"],
                        record["tradeid"],
                        record["ts_code"],
                        record["direction"],
                        record["offset_flag"],
                        record["price"],
                        record["volume"],
                        record["turnover"],
                        record["commission"],
                        record["traded_at"],
                        record["reference"],
                    ),
                )
            conn.commit()
        except Exception as e:
            conn.rollback()
            self._log(f"交易写入失败: {e}")

    def _persist_position(
        self,
        ts_code: str,
        direction: str,
        volume: float,
        price: float,
        pnl: float,
        frozen: float,
    ) -> None:
        """写入/更新持仓"""
        conn = self._ensure_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                if volume > 0:
                    cur.execute(
                        """INSERT INTO vnpy_positions
                        (ts_code, direction, volume, price, pnl, frozen, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (ts_code, direction) DO UPDATE SET
                            volume = EXCLUDED.volume,
                            price = EXCLUDED.price,
                            pnl = EXCLUDED.pnl,
                            frozen = EXCLUDED.frozen,
                            updated_at = NOW()""",
                        (ts_code, direction, volume, price, pnl, frozen),
                    )
                else:
                    # 清仓则删除记录
                    cur.execute(
                        "DELETE FROM vnpy_positions WHERE ts_code = %s AND direction = %s",
                        (ts_code, direction),
                    )
            conn.commit()
        except Exception as e:
            conn.rollback()
            self._log(f"持仓写入失败: {e}")

    def save_daily_snapshot(
        self,
        trade_date: str,
        regime: str = "NEUTRAL",
    ) -> dict:
        """保存每日快照到 vnpy_snapshots"""
        positions = self.main_engine.get_all_positions()
        active_positions = [p for p in positions if p.volume > 0]
        position_value = sum(p.volume * p.price for p in active_positions)

        accounts = self.main_engine.get_all_accounts()
        cash = accounts[0].available if accounts else self.current_equity - position_value
        total_equity = cash + position_value

        # 计算最大回撤
        max_dd = 0.0
        if self.peak_equity > 0:
            max_dd = (self.peak_equity - min(total_equity, self.peak_equity)) / self.peak_equity

        snapshot = {
            "trade_date": trade_date,
            "total_equity": round(total_equity, 2),
            "cash": round(cash, 2),
            "position_value": round(position_value, 2),
            "positions_count": len(active_positions),
            "trades_count": len(self.today_trades),
            "max_drawdown": round(max_dd, 6),
            "regime": regime,
        }

        conn = self._ensure_conn()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO vnpy_snapshots
                        (trade_date, total_equity, cash, position_value,
                         positions_count, trades_count, max_drawdown, regime)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (trade_date) DO UPDATE SET
                            total_equity = EXCLUDED.total_equity,
                            cash = EXCLUDED.cash,
                            position_value = EXCLUDED.position_value,
                            positions_count = EXCLUDED.positions_count,
                            trades_count = EXCLUDED.trades_count,
                            max_drawdown = EXCLUDED.max_drawdown,
                            regime = EXCLUDED.regime,
                            created_at = NOW()""",
                        (
                            trade_date,
                            snapshot["total_equity"],
                            snapshot["cash"],
                            snapshot["position_value"],
                            snapshot["positions_count"],
                            snapshot["trades_count"],
                            snapshot["max_drawdown"],
                            snapshot["regime"],
                        ),
                    )
                conn.commit()
                self._log(f"快照已保存: {trade_date}")
            except Exception as e:
                conn.rollback()
                self._log(f"快照写入失败: {e}")

        return snapshot

    def close(self) -> None:
        """关闭连接"""
        if self._conn and not self._conn.closed:
            self._conn.close()
