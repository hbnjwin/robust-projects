"""
pytest fixtures for factor_engine integration tests.
"""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """
    Generate sample OHLCV data: 10 stocks × 30 trading days.

    Columns: ts_code, trade_date, open, high, low, close, volume
    """
    np.random.seed(42)

    ts_codes = [f"S{i:02d}.SH" for i in range(10)]
    dates = pd.bdate_range("2024-01-02", periods=30)

    rows = []
    for code in ts_codes:
        base_price = np.random.uniform(20, 100)
        for date in dates:
            daily_vol = np.random.uniform(0.005, 0.015)
            close = base_price * (1 + np.random.normal(0, daily_vol))
            open_ = base_price * (1 + np.random.normal(0, daily_vol * 0.5))
            high = max(open_, close) * (1 + abs(np.random.normal(0, 0.005)))
            low = min(open_, close) * (1 - abs(np.random.normal(0, 0.005)))
            volume = int(np.random.uniform(5e5, 5e6))
            rows.append(
                {
                    "ts_code": code,
                    "trade_date": date,
                    "open": round(open_, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                }
            )
            base_price = close  # next day builds on today's close

    return pd.DataFrame(rows)
