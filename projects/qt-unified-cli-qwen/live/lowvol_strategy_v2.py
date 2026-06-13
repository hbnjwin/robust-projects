import pandas as pd
import numpy as np


class LowVolStrategy:

    def __init__(self, lookback=20, top_n=5,
                 base_stop_loss=0.12, strategy_dd_limit=0.20,
                 base_cooldown=5, rebalance_interval=5):
        self.lookback = lookback
        self.top_n = top_n
        self.history = {}
        self.in_position = {}

        # 自适应止损：基础参数
        self.base_stop_loss = base_stop_loss
        self.strategy_dd_limit = strategy_dd_limit  # 默认 0.20，CRISIS 下会被 AdaptiveConfig 覆盖
        self.base_cooldown = base_cooldown
        self.buy_prices = {}
        self.buy_dates = {}          # 记录买入日期（用于持仓天数衰减）
        self.holding_days = {}       # 持仓天数计数器
        self.peak_equity = 0.0
        self.cooldown_remaining = 0
        self.day_count = 0           # 全局交易日计数

        # 调仓频率控制
        self.rebalance_interval = rebalance_interval
        self.days_since_rebalance = 0
        self.last_selected = set()

        # 自适应止损：市场波动率跟踪
        self.market_returns = []  # 全市场平均收益率序列
        self.vol_history_len = 60  # 用于计算长期波动率基准
        self.current_regime = "NEUTRAL"  # 外部注入

    def set_regime(self, regime):
        """由 ReplayEngine 注入当前 Regime"""
        self.current_regime = regime

    def _adaptive_stop_loss(self, code=None):
        """
        自适应止损阈值 v2：
        - Regime 调整（CRISIS 收紧、BULL 放宽）
        - 波动率自适应（短期/长期波动率比值）
        - 持仓天数衰减：持仓越久止损越紧（阴跌保护）
        - 浮亏加速：浮亏越大止损越敏感（非线性）
        - 市场趋势过滤：连续下跌时主动收紧
        """
        # 1. Regime 调整系数
        if self.current_regime == "CRISIS":
            regime_mult = 0.6
            cooldown_mult = 0.5
        elif self.current_regime == "BULL":
            regime_mult = 1.2
            cooldown_mult = 0.6
        else:
            regime_mult = 1.0
            cooldown_mult = 1.0

        # 2. 波动率自适应
        vol_mult = 1.0
        if len(self.market_returns) >= 20:
            short_vol = np.std(self.market_returns[-10:])
            long_vol = np.std(self.market_returns[-self.vol_history_len:]) if len(self.market_returns) >= self.vol_history_len else np.std(self.market_returns)
            if long_vol > 0:
                vol_ratio = short_vol / long_vol
                vol_mult = max(0.7, min(vol_ratio, 2.0))

        # 3. 市场趋势过滤：最近 10 天平均收益为负 → 收紧止损
        trend_mult = 1.0
        if len(self.market_returns) >= 10:
            recent_avg = np.mean(self.market_returns[-10:])
            if recent_avg < -0.002:       # 日均跌 0.2% 以上
                trend_mult = 0.7          # 收紧 30%
            elif recent_avg < -0.001:     # 日均跌 0.1% 以上
                trend_mult = 0.85         # 收紧 15%

        base_sl = self.base_stop_loss * regime_mult * vol_mult * trend_mult

        # 4. 个股级别：持仓天数衰减 + 浮亏加速
        if code and code in self.holding_days and code in self.buy_prices:
            days_held = self.holding_days.get(code, 0)
            buy_price = self.buy_prices[code]

            # 持仓天数衰减：每持仓 5 天，止损收紧 5%（最多收紧 40%）
            time_decay = max(0.6, 1.0 - (days_held // 5) * 0.05)
            base_sl *= time_decay

            # 浮亏加速：当前浮亏超过止损线的 50% 时，加速收紧
            # 例如止损线 10%，浮亏 5% 时开始加速
            if code in self._current_prices:
                current_price = self._current_prices[code]
                if buy_price > 0:
                    current_loss = (buy_price - current_price) / buy_price
                    if current_loss > base_sl * 0.5:
                        # 浮亏越接近止损线，止损线越收紧
                        accel = 1.0 - (current_loss - base_sl * 0.5) / (base_sl * 0.5) * 0.3
                        accel = max(0.7, min(accel, 1.0))
                        base_sl *= accel

        adaptive_sl = max(0.04, min(base_sl, 0.25))

        adaptive_cd = int(self.base_cooldown * cooldown_mult)
        adaptive_cd = max(2, min(adaptive_cd, 15))

        return adaptive_sl, adaptive_cd

    def _update_market_returns(self, price_dict):
        """更新全市场平均收益率"""
        daily_returns = []
        for code, prices in self.history.items():
            if len(prices) >= 2:
                prev = prices[-2]
                curr = prices[-1]
                if prev > 0:
                    daily_returns.append((curr - prev) / prev)
        if daily_returns:
            avg_ret = np.mean(daily_returns)
            self.market_returns.append(avg_ret)
            if len(self.market_returns) > self.vol_history_len * 2:
                self.market_returns = self.market_returns[-self.vol_history_len * 2:]

    def generate(self, date, price_dict):

        self.day_count += 1
        self._current_prices = {code: data["close"] for code, data in price_dict.items()}

        for code, data in price_dict.items():
            self.history.setdefault(code, []).append(data["close"])
            if len(self.history[code]) > self.lookback * 3:
                self.history[code] = self.history[code][-self.lookback * 3:]

        # 更新市场收益率（用于波动率自适应）
        self._update_market_returns(price_dict)

        # 更新持仓天数
        for code in list(self.holding_days.keys()):
            if code in self.in_position:
                self.holding_days[code] = self.holding_days.get(code, 0) + 1

        orders = []

        # 冷却期检查
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return orders

        # 单票止损检查（使用个股级自适应阈值）
        for code in list(self.in_position.keys()):
            if code in self.buy_prices and code in price_dict:
                current_price = price_dict[code]["close"]
                buy_price = self.buy_prices[code]
                # 个股级自适应止损（含持仓天数衰减 + 浮亏加速）
                adaptive_sl, _ = self._adaptive_stop_loss(code=code)
                if buy_price > 0 and (buy_price - current_price) / buy_price >= adaptive_sl:
                    orders.append({"action": "sell", "ts_code": code, "reason": "adaptive_stop"})
                    del self.in_position[code]
                    del self.buy_prices[code]
                    self.holding_days.pop(code, None)

        # 策略级止损检查
        _, adaptive_cd = self._adaptive_stop_loss()
        equity_approx = 0.0
        position_count = 0
        for code in list(self.in_position.keys()):
            if code in price_dict:
                equity_approx += price_dict[code]["close"]
                position_count += 1
        if self.peak_equity == 0.0 and position_count > 0:
            self.peak_equity = equity_approx
        if equity_approx > self.peak_equity:
            self.peak_equity = equity_approx
        if self.peak_equity > 0 and position_count > 0:
            strategy_dd = (self.peak_equity - equity_approx) / self.peak_equity
            if strategy_dd >= self.strategy_dd_limit:
                for code in list(self.in_position.keys()):
                    orders.append({"action": "sell", "ts_code": code, "reason": "strategy_stop"})
                self.in_position.clear()
                self.buy_prices.clear()
                self.holding_days.clear()
                self.cooldown_remaining = adaptive_cd
                self.peak_equity = 0.0
                return orders

        # 调仓频率控制
        self.days_since_rebalance += 1

        vol_list = []
        for code, prices in self.history.items():
            if len(prices) >= self.lookback:
                series = pd.Series(prices[-self.lookback:])
                returns = series.pct_change().dropna()
                if len(returns) > 0:
                    vol = returns.std()
                    vol_list.append((code, vol))

        if not vol_list:
            return orders

        vol_list.sort(key=lambda x: x[1])
        new_selected = set(code for code, _ in vol_list[:self.top_n])

        if self.days_since_rebalance < self.rebalance_interval:
            return orders

        # 缓冲区
        buffer_threshold = int(self.top_n * 1.5)
        expanded_set = set(code for code, _ in vol_list[:buffer_threshold])
        current_held = set(self.in_position.keys())
        if current_held and current_held.issubset(expanded_set) and len(current_held) >= self.top_n:
            return orders

        self.days_since_rebalance = 0
        selected = new_selected

        # 卖出
        for code in list(self.in_position.keys()):
            if code not in selected:
                orders.append({"action": "sell", "ts_code": code})
                del self.in_position[code]
                if code in self.buy_prices:
                    del self.buy_prices[code]
                self.holding_days.pop(code, None)

        # 买入
        for code in selected:
            if code not in self.in_position:
                orders.append({"action": "buy", "ts_code": code})
                self.in_position[code] = True
                self.holding_days[code] = 0
                if code in price_dict:
                    self.buy_prices[code] = price_dict[code]["close"]

        self.last_selected = selected
        return orders
