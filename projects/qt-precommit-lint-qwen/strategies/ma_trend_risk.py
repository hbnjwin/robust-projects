import pandas as pd


class MATrendRiskStrategy:
    def __init__(self, short=10, long=30, trend=200, stop_loss=0.08, position_ratio=0.3):
        self.short = short
        self.long = long
        self.trend = trend
        self.stop_loss = stop_loss
        self.position_ratio = position_ratio
        self.prices = []
        self.entry_price = None

    def on_bar(self, bar):
        self.prices.append(bar["close"])

        if len(self.prices) < self.trend:
            return {"action": "hold", "size": 0}

        s = pd.Series(self.prices)
        short_ma = s.rolling(self.short).mean().iloc[-1]
        long_ma = s.rolling(self.long).mean().iloc[-1]
        trend_ma = s.rolling(self.trend).mean().iloc[-1]
        price = bar["close"]

        # 止损
        if self.entry_price and price < self.entry_price * (1 - self.stop_loss):
            self.entry_price = None
            return {"action": "sell", "size": "all"}

        # 趋势过滤 + 金叉
        if price > trend_ma and short_ma > long_ma and self.entry_price is None:
            self.entry_price = price
            return {"action": "buy", "size": 30}

        # 死叉卖出
        if short_ma < long_ma and self.entry_price is not None:
            self.entry_price = None
            return {"action": "sell", "size": "all"}

        return {"action": "hold", "size": 0}
