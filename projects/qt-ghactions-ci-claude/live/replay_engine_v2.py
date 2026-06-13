from live.portfolio_state_v2 import PortfolioState
from live.execution_engine_v2 import ExecutionEngine
from live.data_loader import load_market_data
import pandas as pd

class ReplayEngine:

    def __init__(self, strategy, market_data,
                 start_date, end_date,
                 initial_capital=1_000_000):

        self.strategy = strategy
        self.market_data = market_data
        self.start_date = start_date
        self.end_date = end_date

        self.portfolio = PortfolioState(initial_capital)
        self.execution = ExecutionEngine(self.portfolio)

        self.loss_streak = 0
        self.cooldown_days = 0
        self.prev_equity = initial_capital

        # 指数加载 — 优先 000300.SH，不存在则用 600519.SH 作为大盘代理
        INDEX_CANDIDATES = ["000300.SH", "600519.SH", "000001.SZ"]
        rows = []
        for candidate in INDEX_CANDIDATES:
            index_raw = load_market_data(start_date, end_date, ts_code=candidate)
            for date, d in index_raw.items():
                if candidate in d:
                    entry = d[candidate]
                    price = entry["close"] if isinstance(entry, dict) else entry
                    rows.append({"date": date, "price": price})
            if rows:
                break  # 找到数据就停止

        if not rows:
            # 完全没有指数数据，禁用趋势过滤（始终视为牛市）
            self._index_lookup = None
            self.index_df = pd.DataFrame(columns=["date", "price"])
        else:
            self.index_df = pd.DataFrame(rows).sort_values("date")
            self.index_df["ma20"] = self.index_df["price"].rolling(20).mean()
            self.index_df["ma60"] = self.index_df["price"].rolling(60).mean()

            # 构建 dict 查找表，避免每次 O(n) 扫描
            self._index_lookup = {}
            for _, row in self.index_df.iterrows():
                self._index_lookup[row["date"]] = {
                    "ma20": row["ma20"],
                    "ma60": row["ma60"],
                }

    def index_is_bull(self, date):
        if self._index_lookup is None:
            return True  # 无指数数据，不过滤
        entry = self._index_lookup.get(date)
        if entry is None:
            return False
        ma20 = entry["ma20"]
        ma60 = entry["ma60"]
        if pd.isna(ma20) or pd.isna(ma60):
            return False
        return ma20 > ma60

    def position_scale(self, drawdown):
        if drawdown < 0.05:
            return 1.0
        elif drawdown < 0.10:
            return 0.7
        elif drawdown < 0.15:
            return 0.4
        else:
            return 0.2

    def run(self):
        for date, prices in self.market_data.items():

            # T+1 执行
            self.execution.execute(prices)

            drawdown = self.portfolio.mark_to_market(prices)
            current_equity = self.portfolio.total_equity

            # 单日收益判断
            daily_return = (current_equity - self.prev_equity) / self.prev_equity
            if daily_return < 0:
                self.loss_streak += 1
            else:
                self.loss_streak = 0

            if self.loss_streak >= 2:
                self.cooldown_days = 5

            self.prev_equity = current_equity

            if self.cooldown_days > 0:
                self.cooldown_days -= 1
                self.portfolio.record(date, drawdown)
                continue

            # 最大回撤风控
            if drawdown > 0.25:
                for code in list(self.portfolio.positions.keys()):
                    self.execution.queue_orders([
                        {"action": "sell", "ts_code": code}
                    ])
                self.portfolio.record(date, drawdown)
                continue

            # 趋势过滤
            if not self.index_is_bull(date):
                self.portfolio.record(date, drawdown)
                continue

            signals = self.strategy.generate(date, prices)

            scale = self.position_scale(drawdown)

            orders = []
            for s in signals:
                orders.append({
                    "action": "buy",
                    "ts_code": s["ts_code"],
                    "scale": scale
                })

            self.execution.queue_orders(orders)

            drawdown = self.portfolio.mark_to_market(prices)
            self.portfolio.record(date, drawdown)

        return self.portfolio.equity_curve
