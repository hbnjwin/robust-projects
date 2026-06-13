"""
live/paper_gateway.py — 模拟盘 Gateway

行情来源: 腾讯实时接口（盘中）/ Tushare 日线（收盘后）
撮合逻辑: 收盘价成交，复用 DailyMatcher
用途: QMT 申请下来前完整验证实盘链路

特性:
  - 真实行情（腾讯接口），非历史回放
  - 订单当日收盘撮合，T+1 / 涨跌停 / 成交量约束
  - 持仓/资金状态持久化到 paper_state.json
  - 与 LiveEngine 接口完全一致，切换 QMT 只需换 Gateway
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.gateway import BaseGateway
from core.oms import OmsEngine, Order, OrderSide, OrderStatus
from core.matcher import DailyMatcher
from live.strategy_account import StrategyAccount

_STATE_PATH = Path(__file__).resolve().parent.parent / "data" / "paper_state.json"


class PaperGateway(BaseGateway):
    """
    模拟盘 Gateway

    用法:
        gw = PaperGateway(initial_cash=1_000_000)
        gw.connect()
        quotes = gw.fetch_quotes(["000001.SZ", "600000.SH"])
        gw.on_daily_close(date, prices)   # 每日收盘后调用，触发撮合
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000,
        slippage: float = 0.001,
        state_path: str | None = None,
    ):
        super().__init__("PaperGateway")
        self._initial_cash = initial_cash
        self._slippage = slippage
        self._state_path = Path(state_path) if state_path else _STATE_PATH

        # 内部账户（单一 paper 账户）
        self._account = StrategyAccount("Paper", initial_cash)

        # OMS + 撮合器
        self._oms = OmsEngine()
        self._matcher = DailyMatcher(self._oms, slippage=slippage)

        # 订阅列表
        self._subscribed: set[str] = set()

        # 加载持久化状态
        self._load_state()

    # ── BaseGateway 接口实现 ─────────────────────────────────

    def connect(self, setting: dict | None = None) -> bool:
        self._connected = True
        self.write_log(f"模拟盘已连接，账户资金: {self._account.cash:,.0f}")
        return True

    def disconnect(self) -> None:
        self._save_state()
        self._connected = False
        self.write_log("模拟盘已断开，状态已保存")

    def subscribe(self, ts_codes: list[str]) -> None:
        self._subscribed.update(ts_codes)
        self.write_log(f"订阅行情: {len(self._subscribed)} 只")

    def send_order(self, order: Order) -> str:
        """接收 OMS Order，加入待撮合队列"""
        # Paper 模式：直接复用传入的 order，标记为 NOTTRADED 等待收盘撮合
        order.status = OrderStatus.NOTTRADED
        self._oms._orders[order.order_id] = order
        self._oms._active[order.order_id] = order
        self.write_log(
            f"挂单: {order.order_id} {order.side.value} "
            f"{order.ts_code} x{order.volume} @{order.price:.2f}"
        )
        return order.order_id

    def cancel_order(self, order_id: str) -> bool:
        result = self._oms.cancel_order(order_id, reason="手动撤单")
        if result:
            self.write_log(f"撤单成功: {order_id}")
        return result

    def query_account(self) -> dict:
        return {
            "balance":   round(self._account.total_equity, 2),
            "available": round(self._account.cash, 2),
            "frozen":    0.0,
        }

    def query_positions(self) -> dict:
        return {
            code: {
                "shares":       pos["shares"],
                "avg_cost":     round(pos.get("avg_cost", 0), 4),
                "market_value": round(
                    pos["shares"] * self._account.last_known_prices.get(code, pos.get("avg_cost", 0)), 2
                ),
            }
            for code, pos in self._account.positions.items()
        }

    # ── Paper 专用接口 ────────────────────────────────────────

    def fetch_quotes(self, ts_codes: list[str] | None = None) -> dict:
        """
        拉取腾讯实时行情
        返回格式与 load_market_data_fast 兼容:
        {ts_code: {close, volume, prev_close}}
        """
        codes = list(ts_codes or self._subscribed)
        if not codes:
            return {}

        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from services.realtime_quotes import get_realtime_quotes
            raw = get_realtime_quotes(codes)
            result = {}
            for ts_code, q in raw.items():
                price     = q.get("price", 0)
                pre_close = q.get("pre_close", 0)
                volume    = q.get("volume", 0)
                if price > 0 and pre_close > 0:
                    result[ts_code] = {
                        "close":      price,
                        "volume":     volume,
                        "prev_close": pre_close,
                    }
            return result
        except Exception as e:
            self.write_log(f"行情拉取失败: {e}")
            return {}

    def on_daily_close(self, date: str, prices: dict) -> dict:
        """
        每日收盘后调用，触发撮合并更新持仓估值

        Parameters
        ----------
        date   : "YYYY-MM-DD"
        prices : {ts_code: {close, volume, prev_close}}

        Returns
        -------
        dict: 当日撮合结果摘要
        """
        # 撮合：Paper 模式所有策略共用同一账户，映射所有可能的策略名
        accounts = {name: self._account for name in
                    ["Paper", "Trend", "LowVol", "Factor", "Cash"]}
        self._matcher.match(date, prices, accounts)

        # 估值
        self._account.mark_to_market(prices)

        # 推送账户更新回调
        if self.on_account:
            self.on_account(self.query_account())

        # 推送成交回调
        trades = self._oms.get_trades()
        for trade in trades:
            if trade.trade_time == date and self.on_trade:
                self.on_trade(trade.to_dict())

        # 持久化
        self._save_state()

        stats = self._oms.get_stats()
        summary = {
            "date":          date,
            "total_equity":  round(self._account.total_equity, 2),
            "cash":          round(self._account.cash, 2),
            "positions":     len(self._account.positions),
            "filled_today":  sum(
                1 for t in self._oms.get_trades() if t.trade_time == date
            ),
            "oms_stats":     stats,
        }
        self.write_log(
            f"[{date}] 收盘撮合完成 equity={summary['total_equity']:,.0f} "
            f"cash={summary['cash']:,.0f} pos={summary['positions']}"
        )

        # 写入 PG
        self._save_to_pg(date, prices)

        return summary

    def _save_to_pg(self, date: str, prices: dict) -> None:
        """将持仓、交易记录、权益写入 PostgreSQL"""
        try:
            import psycopg
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from config import PG_CONFIG
            conn = psycopg.connect(**PG_CONFIG)
            cur  = conn.cursor()

            # 持仓快照
            for code, pos in self._account.positions.items():
                mkt_price = prices.get(code, {}).get("close", pos.get("avg_cost", 0))
                mkt_val   = round(pos["shares"] * mkt_price, 2)
                pnl_pct   = round((mkt_price / pos["avg_cost"] - 1) * 100, 4) if pos.get("avg_cost", 0) > 0 else 0
                cur.execute("""
                    INSERT INTO paper_positions
                        (trade_date, ts_code, shares, avg_cost, market_price, market_value, pnl_pct)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trade_date, ts_code) DO UPDATE
                    SET shares=EXCLUDED.shares, avg_cost=EXCLUDED.avg_cost,
                        market_price=EXCLUDED.market_price,
                        market_value=EXCLUDED.market_value,
                        pnl_pct=EXCLUDED.pnl_pct
                """, (date, code, pos["shares"], pos.get("avg_cost", 0),
                      mkt_price, mkt_val, pnl_pct))

            # 当日交易记录
            for t in self._account.trade_log:
                if str(t.get("date", "")) == date:
                    cur.execute("""
                        INSERT INTO paper_trades
                            (trade_date, ts_code, action, price, shares, amount, fee, reason)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (date, t["code"], t["action"], t["price"], t["shares"],
                          round(t["price"] * t["shares"], 2), t.get("fee", 0),
                          t.get("reason", "signal")))

            # 权益快照
            total_eq = self._account.total_equity
            cur.execute("""
                INSERT INTO paper_equity
                    (trade_date, total_equity, cash, position_count, max_drawdown)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (trade_date) DO UPDATE
                SET total_equity=EXCLUDED.total_equity,
                    cash=EXCLUDED.cash,
                    position_count=EXCLUDED.position_count
            """, (date, round(total_eq, 2), round(self._account.cash, 2),
                  len(self._account.positions),
                  round(self._account.max_drawdown * 100, 4)))

            conn.commit()
            conn.close()
            self.write_log(f"PG 写入完成: {len(self._account.positions)} 持仓")
        except Exception as e:
            self.write_log(f"PG 写入失败（不影响运行）: {e}")

    def place_order(
        self,
        strategy: str,
        ts_code: str,
        side: OrderSide,
        price: float,
        volume: int,
        date: str = "",
        reason: str = "signal",
    ) -> Order:
        """便捷下单接口，直接提交到 OMS 并转发给 Gateway"""
        order = self._oms.submit_order(
            strategy=strategy,
            ts_code=ts_code,
            side=side,
            price=price,
            volume=volume,
            date=date,
            raw_signal={"reason": reason},
        )
        self.send_order(order)
        return order

    # ── 持久化 ────────────────────────────────────────────────

    def _save_state(self) -> None:
        state = {
            "saved_at":  datetime.now().isoformat(),
            "cash":      self._account.cash,
            "positions": self._account.positions,
            "last_known_prices": self._account.last_known_prices,
            "trade_log": self._account.trade_log[-200:],  # 保留最近200条
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, default=str)

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            with open(self._state_path, encoding="utf-8") as f:
                state = json.load(f)
            self._account.cash = state.get("cash", self._initial_cash)
            self._account.positions = state.get("positions", {})
            self._account.last_known_prices = state.get("last_known_prices", {})
            self._account.trade_log = state.get("trade_log", [])
            self.write_log(
                f"加载持久化状态: cash={self._account.cash:,.0f} "
                f"positions={len(self._account.positions)}"
            )
        except Exception as e:
            self.write_log(f"加载状态失败（使用初始状态）: {e}")
