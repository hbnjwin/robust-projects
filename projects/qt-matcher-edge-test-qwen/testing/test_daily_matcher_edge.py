"""
DailyMatcher 边界场景单元测试

覆盖:
  1) 科创板/创业板 20% 涨跌停限价拒绝
  2) 买入量超过成交量上限时的部分成交
  3) 滑点参数对成交价的影响
  4) 连续两日先买后卖的 T+1 约束
  5) 停牌股票（无行情/价格为0）的撮合行为
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.oms import OmsEngine, OrderSide, OrderStatus
from core.matcher import DailyMatcher
from live.strategy_account import StrategyAccount


# ── fixtures ──────────────────────────────────────────────────

def _make_oms_and_account(cash=10_000_000, slippage=0.001):
    """创建 OMS + 策略账户 + matcher 的通用脚手架"""
    oms = OmsEngine()
    account = StrategyAccount("s1", cash)
    matcher = DailyMatcher(oms, slippage=slippage)
    accounts = {"s1": account}
    return oms, account, matcher, accounts


def _submit_buy(oms, ts_code, volume, strategy="s1", date="2026-06-01"):
    return oms.submit_order(strategy, ts_code, OrderSide.BUY, 0, volume, date=date)


def _submit_sell(oms, ts_code, volume, strategy="s1", date="2026-06-02"):
    return oms.submit_order(strategy, ts_code, OrderSide.SELL, 0, volume, date=date)


# ══════════════════════════════════════════════════════════════
# 1) 科创板 / 创业板 20% 涨跌停限价拒绝
# ══════════════════════════════════════════════════════════════

class TestLimitRange20Pct:
    """科创板(688/689)和创业板(300/301)涨跌幅 20%，超出时拒单"""

    @pytest.mark.parametrize("ts_code,prev_close,close,side,expect_reject", [
        # ── 科创板 688: 涨停买入拒绝 ──
        ("688001.SH", 10.0, 12.0, OrderSide.BUY, True),   # +20% 涨停
        ("688001.SH", 10.0, 11.99, OrderSide.BUY, False), # +19.9% 未涨停
        ("688001.SH", 10.0, 12.5, OrderSide.BUY, True),   # 超涨停
        # ── 科创板 688: 跌停卖出拒绝 ──
        ("688001.SH", 10.0, 8.0, OrderSide.SELL, True),   # -20% 跌停
        ("688001.SH", 10.0, 8.01, OrderSide.SELL, False), # -19.9% 未跌停
        ("688001.SH", 10.0, 7.5, OrderSide.SELL, True),   # 超跌停
        # ── 科创板 689 ──
        ("689001.SH", 20.0, 24.0, OrderSide.BUY, True),   # +20% 涨停
        ("689001.SH", 20.0, 16.0, OrderSide.SELL, True),  # -20% 跌停
        # ── 创业板 300 ──
        ("300001.SZ", 15.0, 18.0, OrderSide.BUY, True),   # +20% 涨停
        ("300001.SZ", 15.0, 17.99, OrderSide.BUY, False),
        ("300001.SZ", 15.0, 12.0, OrderSide.SELL, True),  # -20% 跌停
        ("300001.SZ", 15.0, 12.01, OrderSide.SELL, False),
        # ── 创业板 301 ──
        ("301001.SZ", 50.0, 60.0, OrderSide.BUY, True),   # +20% 涨停
        ("301001.SZ", 50.0, 40.0, OrderSide.SELL, True),  # -20% 跌停
        # ── 主板 600 (10% 涨跌停对照) ──
        ("600000.SH", 10.0, 11.0, OrderSide.BUY, True),   # +10% 涨停 → 拒绝
        ("600000.SH", 10.0, 11.5, OrderSide.BUY, True),   # 超涨停 → 拒绝
        ("600000.SH", 10.0, 10.9, OrderSide.BUY, False),  # 未涨停 → 不拒绝
        ("600000.SH", 10.0, 9.0, OrderSide.SELL, True),   # -10% 跌停 → 拒绝
        ("600000.SH", 10.0, 9.01, OrderSide.SELL, False), # 未跌停 → 不拒绝
    ])
    def test_limit_reject(self, ts_code, prev_close, close, side, expect_reject):
        oms, account, matcher, accounts = _make_oms_and_account()

        # 卖出测试需要先建仓（在更早日期）
        if side == OrderSide.SELL:
            account.positions[ts_code] = {
                "shares": 1000, "avg_cost": prev_close, "buy_date": "2026-05-30",
            }

        if side == OrderSide.BUY:
            order = oms.submit_order("s1", ts_code, side, close, 100, date="2026-06-01")
        else:
            order = oms.submit_order("s1", ts_code, side, close, 1000, date="2026-06-01")

        prices = {ts_code: {"close": close, "volume": 10_000_000, "prev_close": prev_close}}
        matcher.match("2026-06-01", prices, accounts)

        if expect_reject:
            assert order.status == OrderStatus.REJECTED, (
                f"{ts_code} close={close} prev={prev_close} 应被拒单，实际 {order.status}"
            )
        else:
            # 不应被涨跌停拒单（可能因其他原因拒单如资金不足，但非限价原因）
            if order.status == OrderStatus.REJECTED:
                assert "涨停" not in order.reject_reason and "跌停" not in order.reject_reason, (
                    f"{ts_code} 不应因涨跌停被拒，原因: {order.reject_reason}"
                )


# ══════════════════════════════════════════════════════════════
# 2) 买入量超过成交量上限时的部分成交
# ══════════════════════════════════════════════════════════════

class TestVolumeLimitPartialFill:
    """成交量限制: max_allowed = int(volume * 0.05) // lot_size * lot_size"""

    @pytest.mark.parametrize("order_shares,day_volume,expected_fill", [
        # 委托 5000 股，成交量允许 50000*0.05=2500 → 部分成交 2500
        (5000, 50_000, 2500),
        # 委托 1000 股，成交量允许 50000*0.05=2500 → 全部成交 1000
        (1000, 50_000, 1000),
        # 委托 10000 股，成交量允许 100000*0.05=5000 → 部分成交 5000
        (10000, 100_000, 5000),
        # 委托 3000 股，成交量允许 20000*0.05=1000 → 部分成交 1000
        (3000, 20_000, 1000),
        # 极小成交量: volume=100, max=5 股 → 整手约束后 0 → 拒单
        (1000, 100, 0),
        # 成交量刚好允许一手: volume=2000, max=100 → 成交 100
        (500, 2_000, 100),
    ])
    def test_partial_fill(self, order_shares, day_volume, expected_fill):
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"
        price = 10.0

        order = oms.submit_order("s1", ts_code, OrderSide.BUY, price, order_shares, date="2026-06-01")
        prices = {ts_code: {"close": price, "volume": day_volume, "prev_close": 9.8}}
        matcher.match("2026-06-01", prices, accounts)

        if expected_fill == 0:
            assert order.status == OrderStatus.REJECTED, "成交量不足时应拒单"
        elif expected_fill >= order_shares:
            assert order.status == OrderStatus.ALLTRADED, "全额成交时应 ALLTRADED"
            assert order.traded == order_shares
        else:
            # 部分成交：DailyMatcher 单次 match 只调一次 fill_order，
            # 所以 order 状态为 PARTTRADED 或 ALLTRADED（取决于 shares vs remaining）
            assert order.traded == expected_fill, (
                f"期望成交 {expected_fill} 股，实际 {order.traded}"
            )
            assert order.status in (OrderStatus.PARTTRADED, OrderStatus.ALLTRADED)

        # 验证持仓
        if expected_fill > 0:
            assert ts_code in account.positions
            assert account.positions[ts_code]["shares"] == expected_fill

    def test_sell_volume_limit(self):
        """卖出同样受成交量限制"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"
        price = 10.0

        # 先建仓
        account.positions[ts_code] = {
            "shares": 5000, "avg_cost": 9.5, "buy_date": "2026-05-30",
        }

        # 成交量 40000, max_allowed = int(40000*0.05) = 2000
        order = oms.submit_order("s1", ts_code, OrderSide.SELL, price, 5000, date="2026-06-01")
        prices = {ts_code: {"close": price, "volume": 40_000, "prev_close": 9.8}}
        matcher.match("2026-06-01", prices, accounts)

        assert order.traded == 2000, f"卖出应限制在 2000 股，实际 {order.traded}"
        assert account.positions[ts_code]["shares"] == 3000  # 5000 - 2000


# ══════════════════════════════════════════════════════════════
# 3) 滑点参数对成交价的影响
# ══════════════════════════════════════════════════════════════

class TestSlippageImpact:
    """不同滑点档位下的成交价验证"""

    @pytest.mark.parametrize("slippage,close_price,side,expected_exec_price", [
        # 买入: exec_price = close * (1 + slippage)
        (0.0, 10.0, OrderSide.BUY, 10.0),
        (0.001, 10.0, OrderSide.BUY, 10.01),
        (0.002, 10.0, OrderSide.BUY, 10.02),
        (0.005, 10.0, OrderSide.BUY, 10.05),
        (0.01, 10.0, OrderSide.BUY, 10.10),
        (0.001, 25.5, OrderSide.BUY, 25.5255),
        # 卖出: exec_price = close * (1 - slippage)
        (0.0, 10.0, OrderSide.SELL, 10.0),
        (0.001, 10.0, OrderSide.SELL, 9.99),
        (0.002, 10.0, OrderSide.SELL, 9.98),
        (0.005, 10.0, OrderSide.SELL, 9.95),
        (0.01, 10.0, OrderSide.SELL, 9.90),
        (0.001, 25.5, OrderSide.SELL, 25.4745),
    ])
    def test_slippage_price(self, slippage, close_price, side, expected_exec_price):
        oms, account, matcher, accounts = _make_oms_and_account(slippage=slippage)
        ts_code = "600000.SH"
        # prev_close 与 close 相同，确保不触发涨跌停
        prev_close = close_price

        if side == OrderSide.SELL:
            account.positions[ts_code] = {
                "shares": 1000, "avg_cost": 9.5, "buy_date": "2026-05-30",
            }
            order = oms.submit_order("s1", ts_code, side, close_price, 100, date="2026-06-01")
        else:
            order = oms.submit_order("s1", ts_code, side, close_price, 100, date="2026-06-01")

        prices = {ts_code: {"close": close_price, "volume": 10_000_000, "prev_close": prev_close}}
        matcher.match("2026-06-01", prices, accounts)

        assert order.status == OrderStatus.ALLTRADED, f"应全部成交，状态: {order.status} ({order.reject_reason})"

        trades = oms.get_trades()
        assert len(trades) == 1
        actual_price = trades[0].price
        assert abs(actual_price - expected_exec_price) < 1e-6, (
            f"slippage={slippage}, close={close_price}, {side.value}: "
            f"期望成交价 {expected_exec_price}, 实际 {actual_price}"
        )

    def test_zero_slippage_no_cost(self):
        """零滑点时买入成本 = close * shares"""
        oms, account, matcher, accounts = _make_oms_and_account(slippage=0.0)
        ts_code = "600000.SH"
        price = 10.0
        shares = 1000

        cash_before = account.cash
        order = oms.submit_order("s1", ts_code, OrderSide.BUY, price, shares, date="2026-06-01")
        prices = {ts_code: {"close": price, "volume": 10_000_000, "prev_close": price}}
        matcher.match("2026-06-01", prices, accounts)

        trades = oms.get_trades()
        assert trades[0].price == price
        # 持仓成本 = 成交价
        assert account.positions[ts_code]["avg_cost"] == price


# ══════════════════════════════════════════════════════════════
# 4) 连续两日先买后卖的 T+1 约束
# ══════════════════════════════════════════════════════════════

class TestTPlus1TwoDaySequence:
    """完整 T+1 序列: Day1 买入 → Day1 卖被拒 → Day2 卖成功"""

    @pytest.mark.parametrize("ts_code,buy_day,sell_day,sell_should_pass", [
        # 主板
        ("600000.SH", "2026-06-01", "2026-06-01", False),  # 同日卖 → 拒
        ("600000.SH", "2026-06-01", "2026-06-02", True),   # 次日卖 → 通过
        # 科创板
        ("688001.SH", "2026-06-01", "2026-06-01", False),
        ("688001.SH", "2026-06-01", "2026-06-02", True),
        # 创业板
        ("300001.SZ", "2026-06-01", "2026-06-01", False),
        ("300001.SZ", "2026-06-01", "2026-06-02", True),
    ])
    def test_buy_then_sell_sequence(self, ts_code, buy_day, sell_day, sell_should_pass):
        oms, account, matcher, accounts = _make_oms_and_account()
        price = 10.0
        prev_close = 9.5
        prices = {ts_code: {"close": price, "volume": 10_000_000, "prev_close": prev_close}}

        # Day1: 买入
        buy_order = oms.submit_order("s1", ts_code, OrderSide.BUY, price, 1000, date=buy_day)
        matcher.match(buy_day, prices, accounts)
        assert buy_order.status == OrderStatus.ALLTRADED, f"买入应成功: {buy_order.reject_reason}"
        assert ts_code in account.positions
        assert account.positions[ts_code]["buy_date"] == buy_day

        # 卖出
        sell_order = oms.submit_order("s1", ts_code, OrderSide.SELL, price, 1000, date=sell_day)
        matcher.match(sell_day, prices, accounts)

        if sell_should_pass:
            assert sell_order.status == OrderStatus.ALLTRADED, (
                f"次日卖出应成功，实际被拒: {sell_order.reject_reason}"
            )
            assert ts_code not in account.positions, "卖出后应无持仓"
        else:
            assert sell_order.status == OrderStatus.REJECTED, "同日卖出应被 T+1 拒单"
            assert "T+1" in sell_order.reject_reason
            assert ts_code in account.positions, "T+1 拒单后应仍有持仓"

    def test_buy_date_updates_on_add(self):
        """加仓后 buy_date 应更新为加仓日"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"
        price = 10.0
        # prev_close 与 close 相同，确保不触发涨跌停
        prices = {ts_code: {"close": price, "volume": 10_000_000, "prev_close": price}}

        # Day1: 买入 500 股
        oms.submit_order("s1", ts_code, OrderSide.BUY, price, 500, date="2026-06-01")
        matcher.match("2026-06-01", prices, accounts)
        assert account.positions[ts_code]["buy_date"] == "2026-06-01"
        assert account.positions[ts_code]["shares"] == 500

        # Day2: 加仓 500 股
        oms.submit_order("s1", ts_code, OrderSide.BUY, price, 500, date="2026-06-02")
        matcher.match("2026-06-02", prices, accounts)
        assert account.positions[ts_code]["buy_date"] == "2026-06-02", "加仓后 buy_date 应更新"
        assert account.positions[ts_code]["shares"] == 1000

        # Day2: 同日卖出应被拒（以加仓日为 T+1 基准）
        sell_order = oms.submit_order("s1", ts_code, OrderSide.SELL, price, 1000, date="2026-06-02")
        matcher.match("2026-06-02", prices, accounts)
        assert sell_order.status == OrderStatus.REJECTED
        assert "T+1" in sell_order.reject_reason

        # Day3: 卖出成功
        sell_order2 = oms.submit_order("s1", ts_code, OrderSide.SELL, price, 1000, date="2026-06-03")
        matcher.match("2026-06-03", prices, accounts)
        assert sell_order2.status == OrderStatus.ALLTRADED
        assert ts_code not in account.positions


# ══════════════════════════════════════════════════════════════
# 5) 停牌股票的撮合行为
# ══════════════════════════════════════════════════════════════

class TestSuspendedStock:
    """停牌（无行情数据或价格为 0）时的撮合行为"""

    def test_no_market_data_reject(self):
        """股票不在 prices dict 中 → 拒单（无行情数据）"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"

        order = oms.submit_order("s1", ts_code, OrderSide.BUY, 10.0, 1000, date="2026-06-01")
        # prices 中不包含该股票
        matcher.match("2026-06-01", {}, accounts)

        assert order.status == OrderStatus.REJECTED
        assert "无行情" in order.reject_reason

    @pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
    def test_missing_code_in_prices_reject(self, side):
        """prices 中有其他股票但缺少目标股票 → 拒单"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"

        if side == OrderSide.SELL:
            account.positions[ts_code] = {
                "shares": 1000, "avg_cost": 9.5, "buy_date": "2026-05-30",
            }

        order = oms.submit_order("s1", ts_code, side, 10.0, 1000, date="2026-06-01")
        # 只有另一只股票的价格
        other_prices = {
            "000001.SZ": {"close": 20.0, "volume": 1_000_000, "prev_close": 19.0}
        }
        matcher.match("2026-06-01", other_prices, accounts)

        assert order.status == OrderStatus.REJECTED
        assert "无行情" in order.reject_reason

    def test_zero_volume_reject(self):
        """成交量为 0（停牌特征）→ 成交量不足拒单"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"

        order = oms.submit_order("s1", ts_code, OrderSide.BUY, 10.0, 1000, date="2026-06-01")
        prices = {ts_code: {"close": 10.0, "volume": 0, "prev_close": 9.5}}
        matcher.match("2026-06-01", prices, accounts)

        assert order.status == OrderStatus.REJECTED
        assert "成交量" in order.reject_reason

    def test_zero_close_price_limit_reject(self):
        """收盘价为 0 → 触发涨跌停判断（price=0 <= limit_down=0），买入时 exec_price=0 导致异常或拒单"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"

        order = oms.submit_order("s1", ts_code, OrderSide.BUY, 0, 1000, date="2026-06-01")
        # prev_close=0 → limit_up=0, close=0 → price >= limit_up → 涨停拒单
        prices = {ts_code: {"close": 0, "volume": 1_000_000, "prev_close": 0}}
        matcher.match("2026-06-01", prices, accounts)

        assert order.status == OrderStatus.REJECTED

    def test_sell_zero_volume_reject(self):
        """卖出时成交量为 0 → 拒单"""
        oms, account, matcher, accounts = _make_oms_and_account()
        ts_code = "600000.SH"
        account.positions[ts_code] = {
            "shares": 1000, "avg_cost": 9.5, "buy_date": "2026-05-30",
        }

        order = oms.submit_order("s1", ts_code, OrderSide.SELL, 10.0, 1000, date="2026-06-01")
        prices = {ts_code: {"close": 10.0, "volume": 0, "prev_close": 9.5}}
        matcher.match("2026-06-01", prices, accounts)

        assert order.status == OrderStatus.REJECTED
        assert "成交量" in order.reject_reason

    @pytest.mark.parametrize("side", [OrderSide.BUY, OrderSide.SELL])
    def test_multiple_orders_one_suspended(self, side):
        """多只股票同时下单，停牌的不影响其他正常撮合"""
        oms, account, matcher, accounts = _make_oms_and_account()

        suspended = "600999.SH"
        normal = "600000.SH"

        if side == OrderSide.SELL:
            account.positions[suspended] = {
                "shares": 1000, "avg_cost": 9.5, "buy_date": "2026-05-30",
            }
            account.positions[normal] = {
                "shares": 1000, "avg_cost": 9.5, "buy_date": "2026-05-30",
            }

        order_suspended = oms.submit_order("s1", suspended, side, 10.0, 100, date="2026-06-01")
        order_normal = oms.submit_order("s1", normal, side, 10.0, 100, date="2026-06-01")

        prices = {
            # suspended 不在 prices 中
            normal: {"close": 10.0, "volume": 10_000_000, "prev_close": 9.5},
        }
        matcher.match("2026-06-01", prices, accounts)

        assert order_suspended.status == OrderStatus.REJECTED
        assert "无行情" in order_suspended.reject_reason
        assert order_normal.status != OrderStatus.REJECTED or "无行情" not in order_normal.reject_reason, (
            "正常股票不应因行情原因被拒"
        )
