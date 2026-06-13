import warnings
warnings.warn(
    "engine.backtest is deprecated and will be removed in a future release. "
    "Use replay_engine_v5.ReplayEngineV5 via unified_backtest.py instead.",
    DeprecationWarning,
    stacklevel=2,
)


class Backtest:
    def __init__(self, datafeed, strategy, broker, portfolio):
        self.datafeed = datafeed
        self.strategy = strategy
        self.broker = broker
        self.portfolio = portfolio

    def run(self):
        while True:
            bar = self.datafeed.next()
            if bar is None:
                break

            signal = self.strategy.on_bar(bar)

            if signal["action"] != "hold":
                price, fee = self.broker.execute(
                    signal["action"],
                    bar["close"],
                    signal["size"]
                )

                if signal["action"] == "buy":
                    cost = price * signal["size"] + fee
                    if self.portfolio.cash >= cost:
                        self.portfolio.cash -= cost
                        self.portfolio.position += signal["size"]

                elif signal["action"] == "sell":
                    if self.portfolio.position >= signal["size"]:
                        self.portfolio.cash += price * signal["size"] - fee
                        self.portfolio.position -= signal["size"]

            self.portfolio.update(bar["close"])

        return self.portfolio.equity_curve
