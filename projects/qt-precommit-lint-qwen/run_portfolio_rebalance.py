import sqlite3
import pandas as pd
import numpy as np

from engine.datafeed import DataFeed
from engine.broker import Broker
from engine.portfolio import Portfolio
from engine.backtest import Backtest
from strategies.ma_trend_risk import MATrendRiskStrategy
from analytics.metrics import max_drawdown, annual_return

DB_PATH = "data/market.db"
CODES = ['603019.SH','000977.SZ','002230.SZ','688256.SH']


def load_full(ts_code):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        """
        SELECT trade_date, close
        FROM daily_price
        WHERE ts_code = ?
        ORDER BY trade_date ASC
        """,
        conn,
        params=(ts_code,),
    )
    conn.close()
    return df


def run_single(df, cash):
    datafeed = DataFeed(df)
    strategy = MATrendRiskStrategy()
    broker = Broker()
    portfolio = Portfolio(cash=cash)
    bt = Backtest(datafeed, strategy, broker, portfolio)
    return bt.run()


def main():
    equities = []

    for code in CODES:
        df = load_full(code)
        eq = run_single(df, 25000)
        equities.append(eq)

    min_len = min(len(e) for e in equities)
    aligned = np.array([e[:min_len] for e in equities])

    # 每20个交易日再平衡一次等权
    portfolio = []
    total = np.sum(aligned[:,0])
    weights = np.array([0.25]*4)

    for i in range(min_len):
        if i % 20 == 0 and i != 0:
            total = np.sum(aligned[:,i])
            weights = np.array([0.25]*4)
        value = np.sum(aligned[:,i] * weights)
        portfolio.append(value)

    portfolio = np.array(portfolio)

    print("=== Monthly Rebalance Portfolio ===")
    print("Final Equity:", round(portfolio[-1],2))
    print("Annual Return:", round(annual_return(portfolio),4))
    print("Max Drawdown:", round(max_drawdown(portfolio),4))


if __name__ == "__main__":
    main()
