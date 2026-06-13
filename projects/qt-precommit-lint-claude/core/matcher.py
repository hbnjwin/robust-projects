"""
core/matcher.py — 回测撮合引擎

职责:
  - 接收 OmsEngine 中的活跃订单
  - 按日线收盘价撮合（含涨跌停/成交量/T+1 约束）
  - 通过 OmsEngine.fill_order / reject_order 回报结果
  - 与 StrategyAccount 联动更新持仓和现金

设计原则:
  - 撮合逻辑从 ExecutionEngineV3 剥离，职责单一
  - OmsEngine 负责状态，Matcher 负责撮合，Account 负责资金
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.contract import contract_manager
from core.oms import OmsEngine, OrderSide
from live.strategy_account import StrategyAccount


class DailyMatcher:
    """
    日线收盘价撮合器

    每个交易日调用一次 match(date, prices, accounts)，
    处理当日所有活跃订单。
    """

    def __init__(self, oms: OmsEngine, slippage: float = 0.001):
        self.oms = oms
        self.slippage = slippage

    def match(
        self,
        date: str,
        prices: dict,
        accounts: dict[str, StrategyAccount],
    ) -> None:
        """
        撮合当日所有活跃订单

        prices: {ts_code: {"close": float, "volume": float, "prev_close": float}}
        accounts: {strategy_name: StrategyAccount}
        """
        active_orders = self.oms.get_active_orders()

        for order in list(active_orders):
            ts_code = order.ts_code

            # 无行情 → 拒单
            if ts_code not in prices:
                self.oms.reject_order(order.order_id, reason="无行情数据")
                continue

            data = prices[ts_code]
            price      = data["close"]
            volume     = data["volume"]
            prev_close = data["prev_close"]

            cfg         = contract_manager.get(ts_code)
            limit_range = contract_manager.limit_range(ts_code)
            limit_up    = prev_close * (1 + limit_range)
            limit_down  = prev_close * (1 - limit_range)
            lot_size    = cfg.size

            account = accounts.get(order.strategy)
            if account is None:
                self.oms.reject_order(order.order_id, reason=f"找不到账户: {order.strategy}")
                continue

            if order.side == OrderSide.BUY:
                self._match_buy(order, price, volume, limit_up, lot_size, cfg, account, date)
            else:
                self._match_sell(order, price, volume, limit_down, account, date)

    # ── 买入撮合 ─────────────────────────────────────────────
    def _match_buy(self, order, price, volume, limit_up, lot_size, cfg, account, date):
        # 涨停不能买
        if price >= limit_up:
            self.oms.reject_order(order.order_id, reason="涨停无法买入")
            return

        exec_price = price * (1 + self.slippage)
        shares = order.remaining

        # 整手约束
        shares = (shares // lot_size) * lot_size
        if shares <= 0:
            self.oms.reject_order(order.order_id, reason="整手约束后股数为0")
            return

        # 成交量限制（5%）
        max_allowed = (int(volume * 0.05) // lot_size) * lot_size
        if max_allowed <= 0:
            self.oms.reject_order(order.order_id, reason="成交量不足")
            return
        shares = min(shares, max_allowed)

        # 资金检查
        fee_rate = cfg.long_rate
        cost = shares * exec_price
        fee  = cost * fee_rate
        if cost + fee > account.cash:
            # 按可用资金缩减
            shares = int(account.cash / (exec_price * (1 + fee_rate)))
            shares = (shares // lot_size) * lot_size
            if shares <= 0:
                self.oms.reject_order(order.order_id, reason="资金不足")
                return
            cost = shares * exec_price
            fee  = cost * fee_rate

        # 成交
        success = account.buy(order.ts_code, exec_price, shares, date=date)
        if success:
            account.cash -= fee
            account.log_trade(
                date=date, code=order.ts_code, action="buy",
                price=exec_price, shares=shares, fee=fee,
                reason=order.raw_signal.get("reason", "signal"),
            )
            self.oms.fill_order(order.order_id, exec_price, shares, fee, trade_time=date)
        else:
            self.oms.reject_order(order.order_id, reason="账户买入失败")

    # ── 卖出撮合 ─────────────────────────────────────────────
    def _match_sell(self, order, price, volume, limit_down, account, date):
        # 跌停不能卖
        if price <= limit_down:
            self.oms.reject_order(order.order_id, reason="跌停无法卖出")
            return

        if order.ts_code not in account.positions:
            self.oms.reject_order(order.order_id, reason="无持仓")
            return

        pos = account.positions[order.ts_code]

        # T+1
        buy_date = pos.get("buy_date")
        if buy_date and str(buy_date) >= str(date):
            self.oms.reject_order(order.order_id, reason="T+1限制")
            return

        shares = pos["shares"]

        # 成交量限制
        max_allowed = int(volume * 0.05)
        shares = min(shares, max_allowed)
        if shares <= 0:
            self.oms.reject_order(order.order_id, reason="成交量不足")
            return

        exec_price = price * (1 - self.slippage)
        cfg      = contract_manager.get(order.ts_code)
        fee_rate = cfg.short_rate
        revenue  = shares * exec_price
        fee      = revenue * fee_rate

        success = account.sell(order.ts_code, exec_price, shares)
        if success:
            account.cash -= fee
            account.log_trade(
                date=date, code=order.ts_code, action="sell",
                price=exec_price, shares=shares, fee=fee,
                reason=order.raw_signal.get("reason", "signal"),
            )
            self.oms.fill_order(order.order_id, exec_price, shares, fee, trade_time=date)
        else:
            self.oms.reject_order(order.order_id, reason="账户卖出失败")
