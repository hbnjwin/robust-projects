import pandas as pd
from datetime import datetime
from live.replay_engine_v3 import ReplayEngineV3
from live.data_loader import load_market_data


def run_event_replay(start_date, months=6, tag="event"):
    start = pd.to_datetime(start_date)
    end = start + pd.DateOffset(months=months)

    market_data = load_market_data(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))

    engine = ReplayEngineV3(
        market_data=market_data,
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
        initial_capital=1_000_000,
    )

    equity_curve = engine.run()
    df = pd.DataFrame(equity_curve)

    result = {
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "final_equity": df.iloc[-1]["equity"],
        "max_drawdown": df["drawdown"].max(),
        "min_equity": df["equity"].min(),
    }

    return result, df
