"""
Phase 3 集成测试
验证数据层抽象: BaseDataFeed / MemoryDataFeed / DuckDBDataFeed / create_datafeed
"""
import sys
import random
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_market_data(n_days=30, n_stocks=5, start="2024-01-01"):
    """构造假行情数据"""
    from datetime import datetime, timedelta
    data = {}
    base = {f"{i:06d}.SZ": 10.0 + i for i in range(n_stocks)}
    dt = datetime.strptime(start, "%Y-%m-%d")
    for d in range(n_days):
        date = (dt + timedelta(days=d)).strftime("%Y-%m-%d")
        day = {}
        for code, price in base.items():
            prev = price
            close = round(prev * (1 + np.random.normal(0, 0.01)), 2)
            close = max(close, 0.1)
            day[code] = {"close": close, "volume": 1_000_000, "prev_close": prev}
            base[code] = close
        data[date] = day
    return data


def test_base_interface():
    print("\n[T1] BaseDataFeed 接口约定")
    from core.datafeed import BaseDataFeed
    import inspect
    # 确认抽象方法存在
    assert "load_bar_data" in [m for m in dir(BaseDataFeed)]
    assert "iter_bar_data" in [m for m in dir(BaseDataFeed)]
    assert "get_trading_dates" in [m for m in dir(BaseDataFeed)]
    print("  抽象接口定义完整 ✓")
    print("[T1] PASS")


def test_memory_datafeed():
    print("\n[T2] MemoryDataFeed")
    from core.datafeed import MemoryDataFeed

    raw = make_market_data(n_days=20, n_stocks=5, start="2024-01-01")
    feed = MemoryDataFeed(raw)

    # 全量加载
    data = feed.load_bar_data("2024-01-01", "2024-01-31")
    assert len(data) > 0
    first_date = sorted(data.keys())[0]
    first_prices = data[first_date]
    assert all(k in v for v in first_prices.values() for k in ("close", "volume", "prev_close"))
    print(f"  全量加载: {len(data)} 天, {len(first_prices)} 只股票 ✓")

    # 日期过滤
    data2 = feed.load_bar_data("2024-01-05", "2024-01-10")
    assert all("2024-01-05" <= d <= "2024-01-10" for d in data2.keys())
    print(f"  日期过滤: {len(data2)} 天 ✓")

    # 股票过滤
    data3 = feed.load_bar_data("2024-01-01", "2024-01-31", ts_codes=["000000.SZ", "000001.SZ"])
    for prices in data3.values():
        assert all(c in ("000000.SZ", "000001.SZ") for c in prices.keys())
    print(f"  股票过滤: 仅含指定股票 ✓")

    # 流式迭代
    dates_iter = list(feed.iter_bar_data("2024-01-01", "2024-01-31"))
    assert len(dates_iter) == len(data)
    assert dates_iter == sorted(dates_iter, key=lambda x: x[0])
    print(f"  流式迭代: {len(dates_iter)} 天，有序 ✓")

    # 交易日列表
    trading_dates = feed.get_trading_dates("2024-01-01", "2024-01-31")
    assert trading_dates == sorted(trading_dates)
    print(f"  交易日列表: {len(trading_dates)} 天 ✓")

    print("[T2] PASS")


def test_duckdb_datafeed_no_data():
    print("\n[T3] DuckDBDataFeed（无本地文件时抛出 FileNotFoundError）")
    from core.datafeed import DuckDBDataFeed

    feed = DuckDBDataFeed(
        csv_dir="/tmp/nonexistent_csv",
        parquet_path="/tmp/nonexistent.parquet",
    )
    try:
        feed.load_bar_data("2024-01-01", "2024-01-31")
        assert False, "应该抛出 FileNotFoundError"
    except FileNotFoundError as e:
        print(f"  FileNotFoundError 正确抛出: {e} ✓")
    print("[T3] PASS")


def test_create_datafeed_factory():
    print("\n[T4] create_datafeed 工厂函数")
    from core.datafeed import create_datafeed, MemoryDataFeed, DuckDBDataFeed, PostgresDataFeed

    raw = make_market_data(10, 3)

    # memory backend
    feed = create_datafeed("memory", market_data=raw)
    assert isinstance(feed, MemoryDataFeed)
    data = feed.load_bar_data("2024-01-01", "2024-12-31")
    assert len(data) == 10
    print(f"  memory backend: {len(data)} 天 ✓")

    # duckdb backend（无文件，只验证类型）
    feed2 = create_datafeed("duckdb")
    assert isinstance(feed2, DuckDBDataFeed)
    print(f"  duckdb backend 实例化 ✓")

    # postgres backend（只验证类型，不实际连接）
    feed3 = create_datafeed("postgres")
    assert isinstance(feed3, PostgresDataFeed)
    print(f"  postgres backend 实例化 ✓")

    print("[T4] PASS")


def test_datafeed_with_rene():
    print("\n[T5] DataFeed 与 ReplayEngineV5 集成")
    from core.datafeed import MemoryDataFeed
    from live.replay_engine_v5 import ReplayEngineV5

    raw = make_market_data(n_days=50, n_stocks=5, start="2024-01-01")
    feed = MemoryDataFeed(raw)

    # 通过 DataFeed 加载数据，传入 ReplayEngineV5
    all_dates = sorted(raw.keys())
    start = all_dates[15]
    end   = all_dates[-1]
    market_data = feed.load_bar_data(all_dates[0], end)

    engine = ReplayEngineV5(
        market_data=market_data,
        start_date=start,
        end_date=end,
        initial_capital=1_000_000,
        ml_signals={},
    )
    curve = engine.run()
    assert len(curve) > 0
    print(f"  ReplayEngineV5 via DataFeed: {len(curve)} 天, final={curve[-1]['equity']:,.0f} ✓")
    print("[T5] PASS")


def test_df_to_dict_edge_cases():
    print("\n[T6] _df_to_dict 边界情况")
    from core.datafeed import MemoryDataFeed
    import pandas as pd

    # prev_close 为 0 或 NaN 应被过滤
    df = pd.DataFrame([
        {"trade_date": "2024-01-02", "ts_code": "000001.SZ", "close": 10.0, "volume": 1e6, "prev_close": 9.5},
        {"trade_date": "2024-01-02", "ts_code": "000002.SZ", "close": 20.0, "volume": 1e6, "prev_close": 0.0},   # 过滤
        {"trade_date": "2024-01-02", "ts_code": "000003.SZ", "close": 15.0, "volume": 1e6, "prev_close": None},  # 过滤
    ])
    result = MemoryDataFeed._df_to_dict(df)
    assert "000001.SZ" in result["2024-01-02"]
    assert "000002.SZ" not in result["2024-01-02"]
    assert "000003.SZ" not in result["2024-01-02"]
    print("  prev_close=0/NaN 正确过滤 ✓")
    print("[T6] PASS")


if __name__ == "__main__":
    np.random.seed(42)
    try:
        test_base_interface()
        test_memory_datafeed()
        test_duckdb_datafeed_no_data()
        test_create_datafeed_factory()
        test_datafeed_with_rene()
        test_df_to_dict_edge_cases()
        print("\n" + "="*50)
        print("  Phase 3 ALL TESTS PASSED ✓")
        print("="*50)
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        sys.exit(1)
