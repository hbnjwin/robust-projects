class StrategyAccount:
    def __init__(self, name, initial_capital):
        self.name = name
        self.initial_capital = initial_capital

        self.cash = initial_capital
        self.positions = {}
        self.last_known_prices = {}  # 记录最后已知价格

        self.total_equity = initial_capital
        self.max_equity = initial_capital
        self.max_drawdown = 0

        self.equity_curve = []
        self.trade_log = []  # 成交日志

    def buy(self, code, price, shares, date=None):
        cost = price * shares
        if cost > self.cash:
            return False
        self.cash -= cost
        if code not in self.positions:
            self.positions[code] = {"shares": shares, "avg_cost": price, "buy_date": date}
        else:
            old_shares = self.positions[code]["shares"]
            old_cost = self.positions[code].get("avg_cost", price)
            total_shares = old_shares + shares
            self.positions[code]["avg_cost"] = (old_cost * old_shares + price * shares) / total_shares
            self.positions[code]["shares"] = total_shares
            # 加仓时更新买入日期（T+1 以最后一次买入为准）
            self.positions[code]["buy_date"] = date
        return True

    def sell(self, code, price, shares):
        if code not in self.positions:
            return False
        if shares > self.positions[code]["shares"]:
            shares = self.positions[code]["shares"]
        revenue = price * shares
        self.cash += revenue
        self.positions[code]["shares"] -= shares
        if self.positions[code]["shares"] == 0:
            del self.positions[code]
        return True

    def log_trade(self, date, code, action, price, shares, fee, reason=""):
        self.trade_log.append(
            {
                "date": date,
                "code": code,
                "action": action,
                "price": price,
                "shares": shares,
                "fee": fee,
                "reason": reason,
            }
        )

    def mark_to_market(self, prices):
        total = self.cash
        for code, pos in self.positions.items():
            if code in prices:
                p = prices[code]["close"]
                self.last_known_prices[code] = p  # 更新最后已知价格
                total += pos["shares"] * p
            elif code in self.last_known_prices:
                # 用最后已知价格，而不是 0
                total += pos["shares"] * self.last_known_prices[code]
            # 如果两者都没有，才按 0 计（极端情况）
        self.total_equity = total
        if total > self.max_equity:
            self.max_equity = total
        drawdown = (self.max_equity - total) / self.max_equity if self.max_equity else 0
        self.max_drawdown = max(self.max_drawdown, drawdown)
        return drawdown

    def record(self, date):
        self.equity_curve.append({"date": date, "equity": self.total_equity, "drawdown": self.max_drawdown})
