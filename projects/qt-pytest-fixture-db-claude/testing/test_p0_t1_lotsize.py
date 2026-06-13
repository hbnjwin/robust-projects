"""T+1 规则 + 100股整手约束 -- pytest 风格测试."""
import pytest

from live.strategy_account import StrategyAccount
from live.execution_engine_v2 import ExecutionEngine


# ── Fixtures ──────────────────────────────────────────────────

STOCK = "600000.SH"
PRICES = {STOCK: {"close": 10.0, "volume": 1_000_000, "prev_close": 9.8}}


@pytest.fixture()
def account_engine():
    """Fresh account (1M cash) + execution engine."""
    acc = StrategyAccount("Test", 1_000_000)
    eng = ExecutionEngine(acc)
    return acc, eng


# ── T+1 ──────────────────────────────────────────────────────


class TestTPlusOne:
    def test_buy_then_same_day_sell_blocked(self, account_engine):
        acc, eng = account_engine

        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 1000}])
        eng.execute(PRICES, date="2026-03-10")
        assert STOCK in acc.positions
        shares_held = acc.positions[STOCK]["shares"]

        # 同日卖出应被拦截
        eng.queue_orders([{"action": "sell", "ts_code": STOCK}])
        eng.execute(PRICES, date="2026-03-10")
        assert acc.positions[STOCK]["shares"] == shares_held

    def test_next_day_sell_succeeds(self, account_engine):
        acc, eng = account_engine

        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 1000}])
        eng.execute(PRICES, date="2026-03-10")
        assert STOCK in acc.positions

        eng.queue_orders([{"action": "sell", "ts_code": STOCK}])
        eng.execute(PRICES, date="2026-03-11")
        assert STOCK not in acc.positions

    def test_add_position_same_day_sell_blocked(self, account_engine):
        acc, eng = account_engine

        # Day1: 买入
        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 500}])
        eng.execute(PRICES, date="2026-03-10")

        # Day2: 加仓
        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 500}])
        eng.execute(PRICES, date="2026-03-11")
        assert acc.positions[STOCK]["shares"] == 1000

        # Day2: 加仓当天卖出被拦截
        eng.queue_orders([{"action": "sell", "ts_code": STOCK}])
        eng.execute(PRICES, date="2026-03-11")
        assert acc.positions[STOCK]["shares"] == 1000

    def test_add_position_next_day_sell_succeeds(self, account_engine):
        acc, eng = account_engine

        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 500}])
        eng.execute(PRICES, date="2026-03-10")
        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 500}])
        eng.execute(PRICES, date="2026-03-11")

        # Day3: 次日卖出成功
        eng.queue_orders([{"action": "sell", "ts_code": STOCK}])
        eng.execute(PRICES, date="2026-03-12")
        assert STOCK not in acc.positions


# ── 整手约束 ──────────────────────────────────────────────────


class TestLotSize:
    def test_target_cash_rounds_to_100(self, account_engine):
        acc, eng = account_engine
        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "target_cash": 1550}])
        eng.execute(PRICES, date="2026-03-10")
        if STOCK in acc.positions:
            assert acc.positions[STOCK]["shares"] % 100 == 0

    def test_weight_rounds_to_100(self):
        acc = StrategyAccount("Test2", 100_000)
        eng = ExecutionEngine(acc)
        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "weight": 0.1}])
        eng.execute(PRICES, date="2026-03-10")
        if STOCK in acc.positions:
            assert acc.positions[STOCK]["shares"] % 100 == 0

    def test_full_position_rounds_to_100(self):
        acc = StrategyAccount("Test3", 5_550)
        eng = ExecutionEngine(acc)
        eng.queue_orders([{"action": "buy", "ts_code": STOCK}])
        eng.execute(PRICES, date="2026-03-10")
        if STOCK in acc.positions:
            assert acc.positions[STOCK]["shares"] % 100 == 0

    def test_insufficient_funds_no_buy(self):
        acc = StrategyAccount("Test4", 500)
        eng = ExecutionEngine(acc)
        eng.queue_orders([{"action": "buy", "ts_code": STOCK}])
        eng.execute(PRICES, date="2026-03-10")
        assert STOCK not in acc.positions


# ── buy_date 记录 ─────────────────────────────────────────────


class TestBuyDate:
    def test_buy_date_recorded(self, account_engine):
        acc, eng = account_engine
        eng.queue_orders([{"action": "buy", "ts_code": STOCK, "shares": 1000}])
        eng.execute(PRICES, date="2026-03-10")
        assert acc.positions[STOCK].get("buy_date") == "2026-03-10"
