import numpy as np


class RegimeDetectorV2:
    def __init__(self, lookback=20, history_len=120):
        self.lookback = lookback
        self.history_len = history_len  # 保留足够长的历史用于 MA60
        self.index_history = []
        self.return_history = []
        self.volume_history = []
        self.crisis_cooldown = 0  # Crisis 冷却计数器

    def update(self, price, volume=None):
        self.index_history.append(price)
        if len(self.index_history) > self.history_len:
            self.index_history = self.index_history[-self.history_len :]

        if len(self.index_history) > 1:
            r = (self.index_history[-1] - self.index_history[-2]) / self.index_history[-2]
            self.return_history.append(r)
            if len(self.return_history) > self.history_len:
                self.return_history = self.return_history[-self.history_len :]

        if volume is not None:
            self.volume_history.append(volume)
            if len(self.volume_history) > self.history_len:
                self.volume_history = self.volume_history[-self.history_len :]

    def detect(self):
        if len(self.index_history) < self.lookback:
            return "NEUTRAL"

        # Crisis 冷却期：触发后至少 5 天才能恢复
        if self.crisis_cooldown > 0:
            self.crisis_cooldown -= 1
            return "CRISIS"

        prices = np.array(self.index_history)
        returns = np.array(self.return_history)

        # --- Crisis 2.0 条件 ---
        crisis_triggered = False

        # 单日暴跌
        if len(returns) > 0 and returns[-1] <= -0.03:
            crisis_triggered = True

        # 连续两日累计跌幅
        if len(returns) >= 2 and (returns[-1] + returns[-2]) <= -0.05:
            crisis_triggered = True

        # 波动率异常
        if len(returns) >= 20:
            short_vol = np.std(returns[-10:])
            long_vol = np.std(returns[-20:])
            if long_vol > 0 and short_vol > long_vol * 2.5:
                crisis_triggered = True

        if crisis_triggered:
            self.crisis_cooldown = 5  # 5 天冷却期
            return "CRISIS"

        # --- 正常趋势判断（现在 MA60 有足够数据） ---
        ma20 = np.mean(prices[-20:]) if len(prices) >= 20 else np.mean(prices)
        ma60 = np.mean(prices[-60:]) if len(prices) >= 60 else np.mean(prices)

        if ma20 > ma60:
            return "BULL"

        return "NEUTRAL"
