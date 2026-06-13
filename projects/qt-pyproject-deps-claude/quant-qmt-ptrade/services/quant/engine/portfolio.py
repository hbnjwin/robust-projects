class Portfolio:
    def __init__(self, cash=100000):
        self.cash = cash
        self.position = 0
        self.equity_curve = []

    def update(self, price):
        total = self.cash + self.position * price
        self.equity_curve.append(total)
        return total
