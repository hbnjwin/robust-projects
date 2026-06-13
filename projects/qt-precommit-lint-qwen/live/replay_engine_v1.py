# DEPRECATED: 此模块已废弃，请使用 live/ 目录下的对应模块
# =============================================================================
# DEPRECATED — 此模块已废弃
# ReplayEngine V1 已被 replay_engine_v3.py (ReplayEngineV3) 取代。
# 请使用 unified_backtest.py 作为统一入口。
# =============================================================================

from live.simple_strategy import SimpleTrendStrategy
from live.low_vol_strategy import LowVolStrategy


class ReplayEngine:
    def __init__(self, strategy, market_data, start_date, end_date, initial_capital=1_000_000):
        self.market_data = market_data
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital

        self.cash = initial_capital
        self.positions = {}
        self.equity_curve = []
        self.max_equity = initial_capital

        self.trend = SimpleTrendStrategy()
        self.lowvol = LowVolStrategy()

    def run(self):
        for date, prices in self.market_data.items():
            market_value = 0
            for code, shares in self.positions.items():
                if code in prices:
                    market_value += shares * prices[code]["close"]

            total_equity = self.cash + market_value

            if total_equity > self.max_equity:
                self.max_equity = total_equity

            drawdown = (self.max_equity - total_equity) / self.max_equity if self.max_equity else 0

            # ✅ 风控：回撤超过25%清仓
            if drawdown > 0.25:
                self.positions = {}
                self.cash = total_equity
                self.equity_curve.append(
                    {"date": date, "equity": total_equity, "cash": self.cash, "drawdown": drawdown}
                )
                continue

            # ✅ 多策略生成信号
            trend_signal = self.trend.generate(date, prices)
            lowvol_signal = self.lowvol.generate(date, prices)

            # ✅ 简单组合：Trend 40%，LowVol 40%，Cash 20%
            allocation = 0.8  # 总仓位 80%
            investable = self.cash * allocation

            if trend_signal and lowvol_signal:
                codes = [trend_signal[0]["ts_code"], lowvol_signal[0]["ts_code"]]
                self.positions = {}
                for code in codes:
                    if code in prices:
                        price = prices[code]["close"]
                        shares = int((investable / 2) / price)
                        if shares > 0:
                            self.positions[code] = shares
                self.cash -= sum(self.positions[c] * prices[c]["close"] for c in self.positions)

            self.equity_curve.append({"date": date, "equity": total_equity, "cash": self.cash, "drawdown": drawdown})

        return self.equity_curve
