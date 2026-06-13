"""
测试 P0-1: T+1 规则 + P1-4: 100股整手约束
"""
import sys
sys.path.insert(0, "/home/tulin/quant")

from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine


def test_t_plus_1():
    print("=== 测试 T+1 规则 ===")

    account = StrategyAccount("Test", 1_000_000)
    engine = ExecutionEngine(account)

    prices = {
        "600000.SH": {"close": 10.0, "volume": 1_000_000, "prev_close": 9.8}
    }

    # Day1: 买入
    engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 1000}])
    engine.execute(prices, date="2026-03-10")

    assert "600000.SH" in account.positions, "FAIL: 买入未成功"
    shares_after_buy = account.positions["600000.SH"]["shares"]
    print(f"  Day1 买入: {shares_after_buy} 股 OK")

    # Day1: 同日尝试卖出（应被 T+1 拦截）
    engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
    engine.execute(prices, date="2026-03-10")

    assert "600000.SH" in account.positions, "FAIL: T+1 未生效，持仓被卖出"
    assert account.positions["600000.SH"]["shares"] == shares_after_buy, "FAIL: T+1 未生效，股数变化"
    print(f"  Day1 卖出被拦截: 持仓仍为 {account.positions['600000.SH']['shares']} 股 OK")

    # Day2: 次日卖出（应成功）
    engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
    engine.execute(prices, date="2026-03-11")

    sold = "600000.SH" not in account.positions
    assert sold, "FAIL: 次日卖出未成功"
    print("  Day2 卖出成功: 持仓已清空 OK")
    print("  T+1 测试通过\n")


def test_t1_add_position():
    """测试加仓后 T+1 以最后一次买入日期为准"""
    print("=== 测试 T+1 加仓场景 ===")

    account = StrategyAccount("Test", 1_000_000)
    engine = ExecutionEngine(account)

    prices = {
        "600000.SH": {"close": 10.0, "volume": 1_000_000, "prev_close": 9.8}
    }

    # Day1: 买入
    engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 500}])
    engine.execute(prices, date="2026-03-10")
    assert "600000.SH" in account.positions
    print(f"  Day1 买入 500 股 OK")

    # Day2: 加仓
    engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 500}])
    engine.execute(prices, date="2026-03-11")
    assert account.positions["600000.SH"]["shares"] == 1000
    print(f"  Day2 加仓 500 股，总计 1000 股 OK")

    # Day2: 尝试卖出（加仓当天，T+1 应拦截）
    engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
    engine.execute(prices, date="2026-03-11")
    assert "600000.SH" in account.positions, "FAIL: 加仓当天卖出未被拦截"
    assert account.positions["600000.SH"]["shares"] == 1000
    print("  Day2 卖出被拦截 OK")

    # Day3: 卖出成功
    engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
    engine.execute(prices, date="2026-03-12")
    assert "600000.SH" not in account.positions, "FAIL: Day3 卖出未成功"
    print("  Day3 卖出成功 OK")
    print("  T+1 加仓场景测试通过\n")


def test_lot_size():
    print("=== 测试 100 股整手约束 ===")

    account = StrategyAccount("Test", 1_000_000)
    engine = ExecutionEngine(account)

    prices = {
        "600000.SH": {"close": 10.0, "volume": 1_000_000, "prev_close": 9.8}
    }

    # target_cash=1550, 价格约10.01(含滑点), 应买100股
    engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "target_cash": 1550}])
    engine.execute(prices, date="2026-03-10")

    if "600000.SH" in account.positions:
        shares = account.positions["600000.SH"]["shares"]
        assert shares % 100 == 0, f"FAIL: {shares} 不是100整数倍"
        print(f"  target_cash=1550 -> {shares} 股 OK")
    else:
        print("  target_cash=1550 -> 不足100股未买入 OK")

    # 测试 weight 模式
    account2 = StrategyAccount("Test2", 100_000)
    engine2 = ExecutionEngine(account2)
    engine2.queue_orders([{"action": "buy", "ts_code": "600000.SH", "weight": 0.1}])
    engine2.execute(prices, date="2026-03-10")

    if "600000.SH" in account2.positions:
        shares = account2.positions["600000.SH"]["shares"]
        assert shares % 100 == 0, f"FAIL: {shares} 不是100整数倍"
        print(f"  weight=0.1 -> {shares} 股 OK")

    # 测试全仓模式也是整手
    account3 = StrategyAccount("Test3", 5_550)
    engine3 = ExecutionEngine(account3)
    engine3.queue_orders([{"action": "buy", "ts_code": "600000.SH"}])
    engine3.execute(prices, date="2026-03-10")

    if "600000.SH" in account3.positions:
        shares = account3.positions["600000.SH"]["shares"]
        assert shares % 100 == 0, f"FAIL: 全仓 {shares} 不是100整数倍"
        print(f"  全仓模式 -> {shares} 股 OK")

    # 测试金额不足100股时不买入
    account4 = StrategyAccount("Test4", 500)
    engine4 = ExecutionEngine(account4)
    engine4.queue_orders([{"action": "buy", "ts_code": "600000.SH"}])
    engine4.execute(prices, date="2026-03-10")
    assert "600000.SH" not in account4.positions, "FAIL: 不足100股但仍买入"
    print("  资金不足100股 -> 未买入 OK")

    print("  整手约束测试通过\n")


def test_buy_date_recorded():
    print("=== 测试 buy_date 记录 ===")

    account = StrategyAccount("Test", 1_000_000)
    engine = ExecutionEngine(account)

    prices = {
        "600000.SH": {"close": 10.0, "volume": 1_000_000, "prev_close": 9.8}
    }

    engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 1000}])
    engine.execute(prices, date="2026-03-10")

    assert "600000.SH" in account.positions
    buy_date = account.positions["600000.SH"].get("buy_date")
    assert buy_date == "2026-03-10", f"FAIL: buy_date={buy_date}"
    print(f"  buy_date={buy_date} OK")
    print("  buy_date 测试通过\n")


if __name__ == "__main__":
    test_t_plus_1()
    test_t1_add_position()
    test_lot_size()
    test_buy_date_recorded()
    print("=" * 50)
    print("P0-1 (T+1) + P1-4 (整手约束) 全部测试通过 ✅")
