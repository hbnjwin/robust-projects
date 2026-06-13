"""
ExecutionEngine v3 — 接入合约配置体系
向后兼容 v2 接口，新增:
  - 从 ContractManager 读取 pricetick / size / long_rate / short_rate
  - 涨跌幅限制支持科创板/创业板 20%
  - 费率买卖分离（long_rate vs short_rate）
  - 整手约束从合约配置读取 size（默认仍 100）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.contract import contract_manager


class ExecutionEngine:

    def __init__(self, account, slippage=0.001, fee=None):
        """
        fee: 兼容旧接口，传入时作为买卖统一费率覆盖合约配置
             不传则从 ContractManager 按股票读取
        """
        self.account = account
        self.slippage = slippage
        self._fee_override = fee   # None = 使用合约配置
        self.pending_orders = []
        self.current_date = None

    # ── 向后兼容属性 ──────────────────────────────────────────
    @property
    def fee(self):
        return self._fee_override if self._fee_override is not None else 0.0003

    @fee.setter
    def fee(self, v):
        self._fee_override = v

    # ── 公开接口（与 v2 完全一致）────────────────────────────
    def queue_orders(self, orders):
        if isinstance(orders, list):
            self.pending_orders.extend(orders)
        else:
            self.pending_orders.append(orders)

    def execute(self, prices, date=None):
        self.current_date = date

        for order in self.pending_orders:
            code = order["ts_code"]
            if code not in prices:
                continue

            data = prices[code]
            price = data["close"]
            volume = data["volume"]
            prev_close = data["prev_close"]

            # 从合约配置读取参数
            cfg = contract_manager.get(code)
            limit_range = contract_manager.limit_range(code)
            lot_size = cfg.size          # 每手股数
            long_rate = self._fee_override if self._fee_override is not None else cfg.long_rate
            short_rate = self._fee_override if self._fee_override is not None else cfg.short_rate

            limit_up = prev_close * (1 + limit_range)
            limit_down = prev_close * (1 - limit_range)

            if order["action"] == "buy":
                self._execute_buy(order, code, price, volume, exec_data={
                    "limit_up": limit_up,
                    "lot_size": lot_size,
                    "long_rate": long_rate,
                })

            elif order["action"] == "sell":
                self._execute_sell(order, code, price, volume, exec_data={
                    "limit_down": limit_down,
                    "short_rate": short_rate,
                })

        self.pending_orders = []

    # ── 内部执行逻辑 ─────────────────────────────────────────
    def _execute_buy(self, order, code, price, volume, exec_data):
        limit_up = exec_data["limit_up"]
        lot_size = exec_data["lot_size"]
        long_rate = exec_data["long_rate"]

        # 涨停不能买
        if price >= limit_up:
            return

        exec_price = price * (1 + self.slippage)

        # 金额控制优先级：weight > shares > target_cash > 全仓
        if "weight" in order:
            # 用总资产（现金+持仓市值）计算目标金额，而不是仅用现金
            total_equity = self.account.cash + sum(
                pos.get("shares", 0) * pos.get("avg_price", 0)
                for pos in self.account.positions.values()
            )
            target_cash = total_equity * order["weight"]
            shares = int(target_cash / exec_price)
        elif "shares" in order:
            shares = order["shares"]
        elif "target_cash" in order:
            shares = int(order["target_cash"] / exec_price)
        else:
            shares = int(self.account.cash / exec_price)

        # 整手约束
        shares = (shares // lot_size) * lot_size
        if shares <= 0:
            return

        # 成交量限制（10%）
        max_allowed = int(volume * 0.10)
        if max_allowed <= 0:
            return
        if shares > max_allowed:
            shares = (max_allowed // lot_size) * lot_size
            if shares <= 0:
                return

        cost = shares * exec_price
        fee_cost = cost * long_rate
        total_cost = cost + fee_cost

        if total_cost > self.account.cash:
            return

        success = self.account.buy(code, exec_price, shares, date=self.current_date)
        if success:
            self.account.cash -= fee_cost
            self.account.log_trade(
                date=self.current_date,
                code=code,
                action="buy",
                price=exec_price,
                shares=shares,
                fee=fee_cost,
                reason=order.get("reason", "signal"),
            )

    def _execute_sell(self, order, code, price, volume, exec_data):
        limit_down = exec_data["limit_down"]
        short_rate = exec_data["short_rate"]

        # 跌停不能卖
        if price <= limit_down:
            return

        if code not in self.account.positions:
            return

        # T+1
        buy_date = self.account.positions[code].get("buy_date")
        if buy_date is not None and self.current_date is not None:
            if str(buy_date) >= str(self.current_date):
                return

        shares = self.account.positions[code]["shares"]

        # 成交量限制
        max_allowed = int(volume * 0.05)
        if shares > max_allowed:
            shares = max_allowed

        exec_price = price * (1 - self.slippage)
        revenue = shares * exec_price
        fee_cost = revenue * short_rate

        success = self.account.sell(code, exec_price, shares)
        if success:
            self.account.cash -= fee_cost
            self.account.log_trade(
                date=self.current_date,
                code=code,
                action="sell",
                price=exec_price,
                shares=shares,
                fee=fee_cost,
                reason=order.get("reason", "signal"),
            )
