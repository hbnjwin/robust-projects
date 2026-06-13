import numpy as np


class TrendStrategyV2:
    def __init__(self, confirm_days=3, lookback=60, max_positions=15, momentum_lookback=20):
        self.confirm_days = confirm_days
        self.lookback = lookback
        self.max_positions = max_positions
        self.momentum_lookback = momentum_lookback
        self.price_history = {}
        self.confirm_counter = {}
        self.in_position = {}

    def generate(self, date, price_dict):
        signals = []
        buy_candidates = []  # 优化2：收集候选，按动量排序

        for code, data in price_dict.items():
            close = data["close"]
            self.price_history.setdefault(code, []).append(close)
            # 截断历史防止内存膨胀
            if len(self.price_history[code]) > self.lookback * 3:
                self.price_history[code] = self.price_history[code][-self.lookback * 3 :]

            prices = self.price_history[code]
            if len(prices) < self.lookback:
                continue

            ma20 = np.mean(prices[-20:])
            ma60 = np.mean(prices[-60:])

            # 趋势条件
            if ma20 > ma60:
                self.confirm_counter[code] = self.confirm_counter.get(code, 0) + 1
            else:
                self.confirm_counter[code] = 0
                if self.in_position.get(code, False):
                    signals.append({"action": "sell", "ts_code": code})
                    self.in_position[code] = False
                continue

            # 连续确认后加入候选列表
            if self.confirm_counter[code] >= self.confirm_days:
                if not self.in_position.get(code, False):
                    # 优化2：计算动量评分 = 过去 momentum_lookback 日收益率
                    if len(prices) >= self.momentum_lookback + 1:
                        base = prices[-self.momentum_lookback - 1]
                        momentum = (prices[-1] - base) / base if base != 0 else 0.0
                    else:
                        momentum = 0.0
                    buy_candidates.append((code, momentum))

        # 优化2：按动量评分降序排序，优先买入动量最强的股票
        buy_candidates.sort(key=lambda x: x[1], reverse=True)

        current_count = sum(1 for v in self.in_position.values() if v)
        for code, momentum in buy_candidates:
            if current_count >= self.max_positions:
                break
            weight = 1.0 / self.max_positions
            signals.append(
                {
                    "action": "buy",
                    "ts_code": code,
                    "weight": weight,  # 执行引擎用此计算金额
                }
            )
            self.in_position[code] = True
            current_count += 1

        return signals
