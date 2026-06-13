import pandas as pd
from live.replay_engine_v2 import ReplayEngine
from live.lowvol_strategy_v2 import LowVolStrategy
from live.data_loader import load_market_data

start = "2021-02-18"
end = "2021-08-18"

market_data = load_market_data(start, end)
strategy = LowVolStrategy()

engine = ReplayEngine(strategy, market_data, start, end)
curve = engine.run()

df = pd.DataFrame(curve)

print("=== LowVol 2021 Test ===")
print("Final Equity:", df.iloc[-1]["equity"])
print("Max Drawdown:", df["drawdown"].max())
print("Min Equity:", df["equity"].min())
