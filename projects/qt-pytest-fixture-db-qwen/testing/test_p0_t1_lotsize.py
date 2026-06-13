"""
测试 P0-1: T+1 规则 + P1-4: 100股整手约束（pytest 版）
"""
import pytest

from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def prices():
    """标准行情：600000.SH 收盘价 10.0"""
    return {
        "600000.SH": {"close": 10.0, "volume": 1_000_000, "prev_close": 9.8}
    }


@pytest.fixture
def make_engine():
    """
    工厂 fixture：每次调用返回全新的 (account, engine) 对。

    Usage:
        account, engine = make_engine("Test", 1_000_000)
    """
    def _factory(name: str = "Test", cash: float = 1_000_000):
        account = StrategyAccount(name, cash)
        engine = ExecutionEngine(account)
        return account, engine
    return _factory


# ---------------------------------------------------------------------------
# T+1 tests
# ---------------------------------------------------------------------------

class TestTPlus1:
    """T+1 交易规则测试"""

    def test_same_day_sell_blocked(self, make_engine, prices):
        """同日买入后卖出，应被 T+1 拦截"""
        account, engine = make_engine("Test", 1_000_000)

        # Day1: 买入
        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 1000}])
        engine.execute(prices, date="2026-03-10")
        assert "600000.SH" in account.positions

        shares_after_buy = account.positions["600000.SH"]["shares"]

        # Day1: 同日尝试卖出（应被 T+1 拦截）
        engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
        engine.execute(prices, date="2026-03-10")

        assert "600000.SH" in account.positions
        assert account.positions["600000.SH"]["shares"] == shares_after_buy

    def test_next_day_sell_succeeds(self, make_engine, prices):
        """次日卖出应成功"""
        account, engine = make_engine("Test", 1_000_000)

        # Day1: 买入
        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 1000}])
        engine.execute(prices, date="2026-03-10")
        assert "600000.SH" in account.positions

        # Day2: 次日卖出
        engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
        engine.execute(prices, date="2026-03-11")
        assert "600000.SH" not in account.positions

    def test_add_position_resets_t1(self, make_engine, prices):
        """加仓后 T+1 以最后一次买入日期为准"""
        account, engine = make_engine("Test", 1_000_000)

        # Day1: 买入 500 股
        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 500}])
        engine.execute(prices, date="2026-03-10")
        assert "600000.SH" in account.positions

        # Day2: 加仓 500 股
        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 500}])
        engine.execute(prices, date="2026-03-11")
        assert account.positions["600000.SH"]["shares"] == 1000

        # Day2: 加仓当天尝试卖出（T+1 应拦截）
        engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
        engine.execute(prices, date="2026-03-11")
        assert "600000.SH" in account.positions
        assert account.positions["600000.SH"]["shares"] == 1000

        # Day3: 卖出成功
        engine.queue_orders([{"action": "sell", "ts_code": "600000.SH"}])
        engine.execute(prices, date="2026-03-12")
        assert "600000.SH" not in account.positions


# ---------------------------------------------------------------------------
# Lot-size (整手约束) tests
# ---------------------------------------------------------------------------

class TestLotSize:
    """100 股整手约束测试"""

    def test_target_cash_lot_alignment(self, make_engine, prices):
        """target_cash 模式：买入股数应为 100 整数倍"""
        account, engine = make_engine("Test", 1_000_000)

        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "target_cash": 1550}])
        engine.execute(prices, date="2026-03-10")

        if "600000.SH" in account.positions:
            shares = account.positions["600000.SH"]["shares"]
            assert shares % 100 == 0

    def test_weight_mode_lot_alignment(self, make_engine, prices):
        """weight 模式：买入股数应为 100 整数倍"""
        account, engine = make_engine("Test2", 100_000)

        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "weight": 0.1}])
        engine.execute(prices, date="2026-03-10")

        if "600000.SH" in account.positions:
            shares = account.positions["600000.SH"]["shares"]
            assert shares % 100 == 0

    def test_all_in_lot_alignment(self, make_engine, prices):
        """全仓模式：买入股数应为 100 整数倍"""
        account, engine = make_engine("Test3", 5_550)

        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH"}])
        engine.execute(prices, date="2026-03-10")

        if "600000.SH" in account.positions:
            shares = account.positions["600000.SH"]["shares"]
            assert shares % 100 == 0

    def test_insufficient_cash_no_buy(self, make_engine, prices):
        """资金不足 100 股时不应买入"""
        account, engine = make_engine("Test4", 500)

        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH"}])
        engine.execute(prices, date="2026-03-10")

        assert "600000.SH" not in account.positions


# ---------------------------------------------------------------------------
# buy_date recording test
# ---------------------------------------------------------------------------

class TestBuyDate:
    """买入日期记录测试"""

    def test_buy_date_recorded(self, make_engine, prices):
        """买入后 buy_date 应正确记录"""
        account, engine = make_engine("Test", 1_000_000)

        engine.queue_orders([{"action": "buy", "ts_code": "600000.SH", "shares": 1000}])
        engine.execute(prices, date="2026-03-10")

        assert "600000.SH" in account.positions
        assert account.positions["600000.SH"]["buy_date"] == "2026-03-10"
