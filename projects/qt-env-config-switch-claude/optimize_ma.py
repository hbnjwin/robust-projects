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


def load_data():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT trade_date, open, high, low, close, vol
        FROM daily_price
        WHERE ts_code = ?
        ORDER BY trade_date ASC
    """
    df = pd.read_sql(query, conn, params=(TS_CODE,))
    conn.close()
    return df


def run_backtest(data, short, long):
    datafeed = DataFeed(data.copy())
    strategy = MACrossStrategy(short=short, long=long)
    broker = Broker()
    portfolio = Portfolio()

    bt = Backtest(datafeed, strategy, broker, portfolio)
    equity = bt.run()

    ann = annual_return(equity)
    mdd = max_drawdown(equity)
    return ann, mdd


def main():
    data = load_data()
    results = []

    for short in range(5, 21):
        for long in range(20, 101):
            if short >= long:
                continue

            ann, mdd = run_backtest(data, short, long)
            results.append((short, long, ann, mdd))

            print(f"Done: short={short}, long={long}, ann={ann:.4f}, mdd={mdd:.4f}", flush=True)

    results.sort(key=lambda x: x[2], reverse=True)

    print("\nTop 10 by Annual Return:")
    for r in results[:10]:
        print(r)


if __name__ == "__main__":
    main()
