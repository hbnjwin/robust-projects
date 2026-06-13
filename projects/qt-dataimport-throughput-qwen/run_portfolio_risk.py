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
        """
        SELECT trade_date, open, high, low, close, vol
        FROM daily_price
        WHERE ts_code = ?
        ORDER BY trade_date ASC
        """,
        conn,
        params=(ts_code,),
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


def apply_portfolio_stop(equity, stop_dd=0.2):
    peak = equity[0]
    stopped_equity = []
    stopped = False

    for v in equity:
        if not stopped:
            peak = max(peak, v)
            dd = (peak - v) / peak
            if dd > stop_dd:
                stopped = True
                stopped_equity.append(v)
            else:
                stopped_equity.append(v)
        else:
            stopped_equity.append(stopped_equity[-1])

    return np.array(stopped_equity)


def main():
    equities = []

    for code in CODES:
        df = load_data(code)
        eq = run_single(df)
        equities.append(eq)

    min_len = min(len(e) for e in equities)
    aligned = [e[:min_len] for e in equities]

    portfolio_equity = np.sum(aligned, axis=0)
    controlled_equity = apply_portfolio_stop(portfolio_equity, stop_dd=0.2)

    print("=== Portfolio With 20% DD Stop ===")
    print("Final Equity:", round(controlled_equity[-1],2))
    print("Annual Return:", round(annual_return(controlled_equity),4))
    print("Max Drawdown:", round(max_drawdown(controlled_equity),4))


if __name__ == "__main__":
    main()
