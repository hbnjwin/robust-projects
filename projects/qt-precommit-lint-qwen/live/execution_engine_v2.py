class ExecutionEngine:
    def __init__(self, account, slippage=0.001, fee=0.0003):
        self.account = account
        self.slippage = slippage
        self.fee = fee
        self.pending_orders = []
        self.current_date = None

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

            limit_up = prev_close * 1.10
            limit_down = prev_close * 0.90

            if order["action"] == "buy":
                # 涨停限制
                if price >= limit_up:
                    continue

                exec_price = price * (1 + self.slippage)

                # 金额控制优先级：weight > shares > target_cash > 全仓
                if "weight" in order:
                    target_cash = self.account.cash * order["weight"]
                    shares = int(target_cash / exec_price)
                elif "shares" in order:
                    shares = order["shares"]
                elif "target_cash" in order:
                    shares = int(order["target_cash"] / exec_price)
                else:
                    shares = int(self.account.cash / exec_price)

                # A股整手约束：买入必须是100的整数倍
                shares = (shares // 100) * 100

                if shares <= 0:
                    continue

                # 成交量限制（5%）
                max_allowed = int(volume * 0.05)
                if max_allowed <= 0:
                    continue

                if shares > max_allowed:
                    shares = (max_allowed // 100) * 100
                    if shares <= 0:
                        continue

                cost = shares * exec_price
                fee_cost = cost * self.fee
                total_cost = cost + fee_cost

                if total_cost > self.account.cash:
                    continue

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

            elif order["action"] == "sell":
                # 跌停限制
                if price <= limit_down:
                    continue

                if code not in self.account.positions:
                    continue

                # T+1 规则：买入当天不能卖出
                buy_date = self.account.positions[code].get("buy_date")
                if buy_date is not None and self.current_date is not None:
                    if str(buy_date) >= str(self.current_date):
                        continue  # T+1 限制，跳过本次卖出

                shares = self.account.positions[code]["shares"]

                # 成交量限制
                max_allowed = int(volume * 0.05)
                if shares > max_allowed:
                    shares = max_allowed

                exec_price = price * (1 - self.slippage)

                revenue = shares * exec_price
                fee_cost = revenue * self.fee

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

        self.pending_orders = []
