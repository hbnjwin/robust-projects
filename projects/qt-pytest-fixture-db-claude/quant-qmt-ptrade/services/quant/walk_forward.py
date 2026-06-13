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
    df = pd.read_sql(
        f"""
        SELECT trade_date, open, high, low, close, vol
        FROM daily_price
        WHERE ts_code = '{TS_CODE}'
        ORDER BY trade_date ASC
        """,
        conn,
    )
    conn.close()
    return df


def run_bt(data, short, long):
    datafeed = DataFeed(data.copy())
    strategy = MACrossStrategy(short=short, long=long)
    broker = Broker()
    portfolio = Portfolio()
    bt = Backtest(datafeed, strategy, broker, portfolio)
    equity = bt.run()
    return annual_return(equity), max_drawdown(equity)


def main():
    df = load_data()
    split = int(len(df) * 0.7)

    train = df.iloc[:split]
    test = df.iloc[split:]

    best = None

    for short in range(5, 21):
        for long in range(20, 61):
            if short >= long:
                continue
            ann, _ = run_bt(train, short, long)
            if best is None or ann > best[2]:
                best = (short, long, ann)

    short, long, train_ann = best
    test_ann, test_mdd = run_bt(test, short, long)

    print("Best on Train:", best, flush=True)
    print("Test Result:", (test_ann, test_mdd), flush=True)


if __name__ == "__main__":
    main()
