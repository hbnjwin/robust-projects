from dao.postgres_dao import PostgresDAO
from engine.datafeed import DataFeed
from engine.broker import Broker
from engine.portfolio import Portfolio
from engine.backtest import Backtest
from strategies.ma_trend_risk import MATrendRiskStrategy
from analytics.metrics import max_drawdown, annual_return


def main():
    dao = PostgresDAO(
        host='localhost',
        port=5432,
        user='postgres',
        password='limit123',
        dbname='quant'
    )

    df = dao.get_daily_price('603019.SH')

    datafeed = DataFeed(df)
    strategy = MATrendRiskStrategy()
    broker = Broker()
    portfolio = Portfolio()

    bt = Backtest(datafeed, strategy, broker, portfolio)
    equity = bt.run()

    print("=== PostgreSQL Backtest ===")
    print("Final Equity:", round(equity[-1], 2))
    print("Annual Return:", round(annual_return(equity), 4))
    print("Max Drawdown:", round(max_drawdown(equity), 4))

    dao.close()


if __name__ == "__main__":
    main()
