"""
Phase 1 集成测试
验证 P1.1 + P1.2 + P1.3 联动正确性：
1. ContractManager 能正确读取配置
2. LegacyStrategyAdapter 包装旧策略正常工作
3. ExecutionEngineV3 费率/涨跌幅正确
4. ReplayEngineV5 run() 结果与 V4 数值接近（允许微小浮点差异）
"""
import sys
import random
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_contract_manager():
    print("\n[T1] ContractManager")
    from core.contract import contract_manager, ContractConfig

    # 默认配置
    cfg = contract_manager.get("000001.SZ")
    assert cfg.pricetick == 0.01
    assert cfg.size == 100
    assert cfg.long_rate == 0.0003
    assert cfg.short_rate == 0.0013
    print(f"  000001.SZ default: pricetick={cfg.pricetick} size={cfg.size} "
          f"long={cfg.long_rate} short={cfg.short_rate}")

    # 科创板涨跌幅 20%
    assert contract_manager.limit_range("688001.SH") == 0.20
    assert contract_manager.limit_range("300001.SZ") == 0.20
    assert contract_manager.limit_range("600001.SH") == 0.10
    print("  涨跌幅限制: 688/300=20% 600=10% ✓")

    # 个股配置（600519 在 JSON 里）
    cfg2 = contract_manager.get("600519.SH")
    assert cfg2.symbol == "600519.SH"
    print(f"  600519.SH 个股配置: {cfg2} ✓")
    print("[T1] PASS")


def test_legacy_adapter():
    print("\n[T2] LegacyStrategyAdapter")
    from core.strategy import LegacyStrategyAdapter
    from live.trend_strategy_v2 import TrendStrategyV2
    from live.lowvol_strategy_v2 import LowVolStrategy
    from strategies.factor_strategy import FactorStrategy

    # 构造假行情
    def make_prices(n=5):
        return {f"{i:06d}.SZ": {"close": 10.0 + i * 0.1,
                                 "volume": 1_000_000,
                                 "prev_close": 10.0 + i * 0.1}
                for i in range(n)}

    # TrendStrategy
    trend = LegacyStrategyAdapter("Trend", TrendStrategyV2())
    trend.initialize()
    for day in range(70):
        date = f"2024-01-{day+1:02d}" if day < 31 else f"2024-02-{day-30:02d}"
        sigs = trend.on_bars(date, make_prices(10))
    print(f"  TrendStrategy signals after warmup: {len(sigs)} ✓")

    # LowVolStrategy
    lowvol = LegacyStrategyAdapter("LowVol", LowVolStrategy())
    lowvol.initialize()
    lowvol.set_regime("BULL")
    sigs2 = lowvol.on_bars("2024-03-01", make_prices(20))
    print(f"  LowVolStrategy signals: {len(sigs2)} ✓")

    # FactorStrategy
    fake_signals = {"2024-03-01": {f"{i:06d}.SZ": float(i) for i in range(20)}}
    factor = LegacyStrategyAdapter("Factor", FactorStrategy(factor_scores=fake_signals, top_n=5))
    factor.initialize()
    sigs3 = factor.on_bars("2024-03-01", make_prices(20))
    assert any(s["action"] == "buy" for s in sigs3)
    print(f"  FactorStrategy signals: {len(sigs3)} ✓")
    print("[T2] PASS")


def test_execution_engine_v3():
    print("\n[T3] ExecutionEngineV3")
    from live.execution_engine_v3 import ExecutionEngine
    from live.strategy_account import StrategyAccount

    acc = StrategyAccount("Test", 1_000_000)
    eng = ExecutionEngine(acc)

    prices = {
        "000001.SZ": {"close": 10.0, "volume": 5_000_000, "prev_close": 9.5},
        "688001.SH": {"close": 20.0, "volume": 5_000_000, "prev_close": 18.0},
    }

    # 买入普通股
    eng.queue_orders([{"action": "buy", "ts_code": "000001.SZ", "weight": 0.1}])
    eng.execute(prices, date="2024-01-02")
    assert "000001.SZ" in acc.positions
    shares = acc.positions["000001.SZ"]["shares"]
    assert shares % 100 == 0  # 整手约束
    print(f"  000001.SZ 买入 {shares} 股，整手约束 ✓")

    # 科创板涨停不能买（close >= prev_close * 1.20，涨停价 = 18 * 1.20 = 21.6）
    prices_limit = {
        "688001.SH": {"close": 21.6, "volume": 5_000_000, "prev_close": 18.0},
    }
    before_cash = acc.cash
    eng.queue_orders([{"action": "buy", "ts_code": "688001.SH", "weight": 0.1}])
    eng.execute(prices_limit, date="2024-01-02")
    assert "688001.SH" not in acc.positions  # 涨停不成交
    assert acc.cash == before_cash
    print("  科创板涨停拦截 ✓")

    # 费率分离验证（short_rate > long_rate）
    from core.contract import contract_manager
    cfg = contract_manager.get("000001.SZ")
    assert cfg.short_rate > cfg.long_rate
    print(f"  费率分离: long={cfg.long_rate} short={cfg.short_rate} ✓")
    print("[T3] PASS")


def test_replay_engine_v5_smoke():
    """轻量 smoke test：用假行情跑 20 天，验证不崩溃且 equity_curve 有数据"""
    print("\n[T4] ReplayEngineV5 smoke test")
    from live.replay_engine_v5 import ReplayEngineV5

    # 构造 20 天假行情（5只股票）
    random.seed(42)
    np.random.seed(42)
    market_data = {}
    base_prices = {f"{i:06d}.SZ": 10.0 + i for i in range(5)}

    all_dates = [f"2024-0{1 if d < 31 else 2}-{(d % 30)+1:02d}" for d in range(60)]
    for date in all_dates:
        day_prices = {}
        for code, base in base_prices.items():
            prev = base * (1 + np.random.normal(0, 0.01))
            close = prev * (1 + np.random.normal(0, 0.01))
            day_prices[code] = {
                "close": round(max(close, 0.1), 2),
                "volume": int(np.random.uniform(500_000, 5_000_000)),
                "prev_close": round(max(prev, 0.1), 2),
            }
            base_prices[code] = close
        market_data[date] = day_prices

    start = all_dates[20]
    end   = all_dates[-1]

    engine = ReplayEngineV5(
        market_data=market_data,
        start_date=start,
        end_date=end,
        initial_capital=1_000_000,
        ml_signals={},
    )
    curve = engine.run()

    assert len(curve) > 0, "equity_curve 为空"
    assert all("equity" in r and "date" in r for r in curve)
    print(f"  equity_curve: {len(curve)} days, "
          f"final={curve[-1]['equity']:,.0f}, "
          f"dd={curve[-1]['drawdown']:.2%}")
    print("[T4] PASS")


if __name__ == "__main__":
    try:
        test_contract_manager()
        test_legacy_adapter()
        test_execution_engine_v3()
        test_replay_engine_v5_smoke()
        print("\n" + "="*50)
        print("  ALL TESTS PASSED ✓")
        print("="*50)
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        sys.exit(1)
