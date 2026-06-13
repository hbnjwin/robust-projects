import warnings
warnings.warn(
    "engine.portfolio is deprecated and will be removed in a future release. "
    "Use live.portfolio_state_v2.PortfolioState instead.",
    DeprecationWarning,
    stacklevel=2,
)


class Portfolio:
    def __init__(self, cash=100000):
        self.cash = cash
        self.position = 0
        self.equity_curve = []

    def update(self, price):
        total = self.cash + self.position * price
        self.equity_curve.append(total)
        return total
