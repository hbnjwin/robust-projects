import sqlite3
import pandas as pd

from engine.datafeed import DataFeed
from engine.broker import Broker
from engine.portfolio import Portfolio
from engine.backtest import Backtest
from strategies.ma_cross import MACrossStrategy
from analytics.metrics import max_drawdown, annual_return

DB_PATH = "data/market.db"
TS_CODE = "603019.SH"


def load_data_from_sqlite():
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT trade_date, open, high, low, close, vol
        FROM daily_price
        WHERE ts_code = '{TS_CODE}'
        ORDER BY trade_date ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def run():
    data = load_data_from_sqlite()

    print(f"Loaded rows: {len(data)}")

    datafeed = DataFeed(data)
    strategy = MACrossStrategy(short=5, long=20)
    broker = Broker()
    portfolio = Portfolio()

    bt = Backtest(datafeed, strategy, broker, portfolio)
    equity = bt.run()

    print("Final Equity:", round(equity[-1], 2))
    print("Max Drawdown:", round(max_drawdown(equity), 4))
    print("Annual Return:", round(annual_return(equity), 4))


if __name__ == "__main__":
    run()
