class PortfolioState:
    def __init__(self, initial_capital):
        self.initial_capital = initial_capital
        self.cash = float(initial_capital)
        self.positions = {}
        self.total_equity = float(initial_capital)
        self.max_equity = float(initial_capital)
        self.equity_curve = []

    def mark_to_market(self, price_dict):
        market_value = 0.0
        for code, pos in self.positions.items():
            if code in price_dict:
                market_value += pos["shares"] * price_dict[code]

        self.total_equity = self.cash + market_value

        if self.total_equity > self.max_equity:
            self.max_equity = self.total_equity

        drawdown = (self.max_equity - self.total_equity) / self.max_equity if self.max_equity > 0 else 0
        return drawdown

    def buy(self, code, price, shares):
        cost = price * shares
        if cost > self.cash:
            return False

        if code not in self.positions:
            self.positions[code] = {"shares": shares, "avg_cost": price}
        else:
            old = self.positions[code]
            total_shares = old["shares"] + shares
            new_avg = (old["shares"] * old["avg_cost"] + shares * price) / total_shares
            self.positions[code]["shares"] = total_shares
            self.positions[code]["avg_cost"] = new_avg

        self.cash -= cost
        return True

    def sell(self, code, price, shares):
        if code not in self.positions:
            return False

        pos = self.positions[code]
        if shares > pos["shares"]:
            shares = pos["shares"]

        self.cash += shares * price
        pos["shares"] -= shares

        if pos["shares"] == 0:
            del self.positions[code]
        return True

    def record(self, date, drawdown):
        self.equity_curve.append({"date": date, "equity": self.total_equity, "cash": self.cash, "drawdown": drawdown})
