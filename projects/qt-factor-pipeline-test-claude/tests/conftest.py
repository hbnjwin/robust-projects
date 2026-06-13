"""
tests/conftest.py
Shared fixtures for factor_engine integration tests.
"""
import datetime

import duckdb
import numpy as np
import pandas as pd
import pytest


# ── 10 只股票，30 个交易日 ──────────────────────────────────────

_STOCKS = [f"{i:06d}.SZ" for i in range(1, 11)]
_N_DAYS = 30
_SEED = 42


@pytest.fixture()
def sample_ohlcv() -> pd.DataFrame:
    """
    生成 10 只股票 × 30 个交易日的 OHLCV 小样本。
    使用固定 seed 保证可复现。
    """
    rng = np.random.default_rng(_SEED)

    # 30 个交易日（跳过周末）
    dates = pd.bdate_range("2024-01-02", periods=_N_DAYS)

    rows = []
    for code in _STOCKS:
        # 每只股票从不同基准价开始，模拟价格差异
        base_price = rng.uniform(10, 100)
        price = base_price
        base_volume = rng.uniform(5e5, 5e6)

        for dt in dates:
            # 随机游走
            ret = rng.normal(0.001, 0.025)
            price *= 1 + ret

            # OHLCV
            intraday_vol = abs(rng.normal(0, 0.015))
            o = price * (1 + rng.normal(0, 0.005))
            h = max(o, price) * (1 + intraday_vol)
            l = min(o, price) * (1 - intraday_vol)
            c = price
            v = base_volume * rng.lognormal(0, 0.3)

            rows.append({
                "ts_code": code,
                "trade_date": dt.strftime("%Y-%m-%d"),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": round(v, 0),
            })

    return pd.DataFrame(rows)


@pytest.fixture()
def pipeline_with_data(sample_ohlcv):
    """
    创建一个 FactorPipeline（内存 DuckDB），
    直接将 sample_ohlcv 注册为 prices 表，跳过 PostgreSQL。
    """
    from factor_engine.pipeline import FactorPipeline

    pipe = FactorPipeline(db_path=":memory:")
    # 直接把 DataFrame 灌入 DuckDB，绕过 PG
    # DuckDB 自动扫描 Python 局部变量作为表引用
    pipe.con.execute("CREATE TABLE prices AS SELECT * FROM sample_ohlcv")
    pipe._pg_attached = True  # 阻止后续尝试连接 PG
    yield pipe
    pipe.close()
