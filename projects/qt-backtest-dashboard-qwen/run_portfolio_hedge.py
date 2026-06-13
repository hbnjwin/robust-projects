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
INDEX = '000300.SH'  # 沪深300


def load_close(ts_code):
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

    # 多头组合
    for code in CODES:
        df = load_close(code)
        eq = run_single(df, 25000)
        equities.append(eq)

    min_len = min(len(e) for e in equities)
    aligned = np.array([e[:min_len] for e in equities])
    long_portfolio = np.sum(aligned, axis=0)

    # 指数简单对冲（50%对冲）
    idx_df = load_close('603019.SH')  # 临时用同长度占位
    hedge = long_portfolio * 0.5
    hedged_equity = long_portfolio - hedge

    print("=== Hedged Portfolio (50% synthetic hedge) ===")
    print("Final Equity:", round(hedged_equity[-1],2))
    print("Annual Return:", round(annual_return(hedged_equity),4))
    print("Max Drawdown:", round(max_drawdown(hedged_equity),4))


if __name__ == "__main__":
    main()
