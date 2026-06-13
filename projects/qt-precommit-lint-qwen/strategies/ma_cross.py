import pandas as pd


class MACrossStrategy:
    def __init__(self, short=5, long=20):
        self.short = short
        self.long = long
        self.prices = []
        self._max_len = max(short, long) + 10

    def on_bar(self, bar):
        self.prices.append(bar["close"])

        # 限制历史长度，避免 O(n²) 性能问题
        if len(self.prices) > self._max_len:
            self.prices = self.prices[-self._max_len :]

        if len(self.prices) < self.long:
            return {"action": "hold", "size": 0}

        df = pd.Series(self.prices)
        short_ma = df.rolling(self.short).mean().iloc[-1]
        long_ma = df.rolling(self.long).mean().iloc[-1]

        if short_ma > long_ma:
            return {"action": "buy", "size": 10}
        elif short_ma < long_ma:
            return {"action": "sell", "size": 10}
        else:
            return {"action": "hold", "size": 0}
