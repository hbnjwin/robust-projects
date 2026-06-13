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


def load_data(ts_code):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        f"""
        SELECT trade_date, open, high, low, close, vol
        FROM daily_price
        WHERE ts_code = '{ts_code}'
        ORDER BY trade_date ASC
        """,
        conn,
    )
    conn.close()
    return df


def run_single(df, initial_cash=25000):
    datafeed = DataFeed(df)
    strategy = MATrendRiskStrategy()
    broker = Broker()
    portfolio = Portfolio(cash=initial_cash)
    bt = Backtest(datafeed, strategy, broker, portfolio)
    equity = bt.run()
    return equity


def main():
    equities = []

    for code in CODES:
        df = load_data(code)
        eq = run_single(df)
        equities.append(eq)
        print(code, "final:", round(eq[-1],2))

    min_len = min(len(e) for e in equities)
    aligned = [e[:min_len] for e in equities]

    portfolio_equity = np.sum(aligned, axis=0)

    print("\n=== Portfolio Result ===")
    print("Final Equity:", round(portfolio_equity[-1],2))
    print("Annual Return:", round(annual_return(portfolio_equity),4))
    print("Max Drawdown:", round(max_drawdown(portfolio_equity),4))


if __name__ == "__main__":
    main()
