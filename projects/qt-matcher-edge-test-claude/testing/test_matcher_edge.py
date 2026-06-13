"""
DailyMatcher 边缘场景单元测试

覆盖:
  1. 科创板/创业板 20% 涨跌停限价拒绝
  2. 成交量上限（volume 5%）部分成交
  3. 滑点参数对成交价的影响
  4. 连续两日先买后卖 T+1 约束
  5. 停牌股票（无行情数据）撮合行为
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from core.oms import OmsEngine, OrderSide, OrderStatus
from core.matcher import DailyMatcher
from live.strategy_account import StrategyAccount


# ── fixtures ────────────────────────────────────────────────────

@pytest.fixture
def oms():
    return OmsEngine()


@pytest.fixture
def account():
    return StrategyAccount("test_strat", 10_000_000)


@pytest.fixture
def accounts(account):
    return {"test_strat": account}


def _matcher(oms, slippage=0.001):
    return DailyMatcher(oms, slippage=slippage)


# ═══════════════════════════════════════════════════════════════
# 1. 科创板 / 创业板 20% 涨跌停限价拒绝
# ═══════════════════════════════════════════════════════════════

class TestLimitPrice:
    """涨跌停价格触达时应拒单"""

    @pytest.mark.parametrize("ts_code, prev_close, close, desc", [
        # 科创板 688 涨停买入
        ("688001.SH", 100.0, 120.0, "科创板688涨停买入"),
        # 科创板 689 涨停买入
        ("689001.SH", 50.0,  60.0,  "科创板689涨停买入"),
        # 创业板 300 涨停买入
        ("300001.SZ", 80.0,  96.0,  "创业板300涨停买入"),
        # 创业板 301 涨停买入
        ("301001.SZ", 40.0,  48.0,  "创业板301涨停买入"),
    ])
    def test_buy_rejected_at_limit_up_20pct(
        self, oms, accounts, ts_code, prev_close, close, desc
    ):
        """20% 涨停价买入应拒单"""
        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": prev_close}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "涨停" in order.reject_reason

    @pytest.mark.parametrize("ts_code, prev_close, close, desc", [
        ("688001.SH", 100.0, 80.0, "科创板688跌停卖出"),
        ("689001.SH", 50.0,  40.0, "科创板689跌停卖出"),
        ("300001.SZ", 80.0,  64.0, "创业板300跌停卖出"),
        ("301001.SZ", 40.0,  32.0, "创业板301跌停卖出"),
    ])
    def test_sell_rejected_at_limit_down_20pct(
        self, oms, account, accounts, ts_code, prev_close, close, desc
    ):
        """20% 跌停价卖出应拒单"""
        # 先建立持仓（用前一天买入）
        account.positions[ts_code] = {"shares": 1000, "avg_cost": prev_close, "buy_date": "2026-01-01"}

        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 1000)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": prev_close}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "跌停" in order.reject_reason

    @pytest.mark.parametrize("ts_code, prev_close, close, desc", [
        # 主板 10% 涨停（用略高于限价的 close 避免 float 精度问题: 100*1.1=110.00000000000001）
        ("600000.SH", 100.0, 110.01, "主板涨停买入"),
        ("000001.SZ", 50.0,  55.01,  "深主板涨停买入"),
    ])
    def test_buy_rejected_at_limit_up_10pct(
        self, oms, accounts, ts_code, prev_close, close, desc
    ):
        """主板 10% 涨停价买入应拒单"""
        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": prev_close}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "涨停" in order.reject_reason

    @pytest.mark.parametrize("ts_code, prev_close, close, limit_pct, desc", [
        # 未涨停 — 科创板 close < prev_close * 1.20
        ("688001.SH", 100.0, 119.0, 0.20, "科创板未涨停应成交"),
        # 未涨停 — 主板 close < prev_close * 1.10
        ("600000.SH", 100.0, 109.0, 0.10, "主板未涨停应成交"),
    ])
    def test_buy_accepted_below_limit_up(
        self, oms, accounts, ts_code, prev_close, close, limit_pct, desc
    ):
        """未触及涨停价时应正常成交"""
        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": prev_close}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.status == OrderStatus.ALLTRADED, f"{desc}: 应成交"


# ═══════════════════════════════════════════════════════════════
# 2. 成交量上限（volume * 5%）部分成交
# ═══════════════════════════════════════════════════════════════

class TestVolumeLimitPartialFill:
    """买入量超过当日可用成交量 5% 时应部分成交"""

    @pytest.mark.parametrize("order_shares, volume, expected_shares, desc", [
        # volume=10000, 5%=500, 整手500, 下单1000 → 成交500
        (1000, 10_000, 500,  "超量一倍→部分成交500"),
        # volume=5000, 5%=250, 整手200, 下单1000 → 成交200
        (1000, 5_000,  200,  "5%=250→整手截断为200"),
        # volume=2000, 5%=100, 整手100, 下单500 → 成交100
        (500,  2_000,  100,  "5%=100→整手截断为100"),
        # volume=100000, 5%=5000, 下单200 → 全部成交200（未超量）
        (200,  100_000, 200, "未超量→全部成交"),
    ])
    def test_buy_volume_cap(
        self, oms, accounts, order_shares, volume, expected_shares, desc
    ):
        matcher = _matcher(oms)
        ts_code = "600000.SH"
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, 10.0, order_shares)
        prices = {ts_code: {"close": 10.0, "volume": volume, "prev_close": 10.0}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.traded == expected_shares, f"{desc}: 成交{order.traded} != 期望{expected_shares}"

    @pytest.mark.parametrize("volume, desc", [
        # volume=1000, 5%=50, 整手截断=0 → 拒单
        (1_000, "volume太小→整手截断后为0"),
        # volume=0
        (0,     "volume=0→拒单"),
    ])
    def test_buy_rejected_when_volume_too_small(
        self, oms, accounts, volume, desc
    ):
        """成交量 5% 不足一手时应拒单"""
        matcher = _matcher(oms)
        ts_code = "600000.SH"
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, 10.0, 100)
        prices = {ts_code: {"close": 10.0, "volume": volume, "prev_close": 10.0}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "成交量" in order.reject_reason

    @pytest.mark.parametrize("pos_shares, volume, expected_sold, desc", [
        # 卖出: volume=10000, 5%=500, 持仓1000 → 卖500
        (1000, 10_000, 500,  "卖出超量→部分成交500"),
        # 卖出: volume=100000, 5%=5000, 持仓800 → 全部卖出800
        (800,  100_000, 800, "卖出未超量→全部卖出"),
    ])
    def test_sell_volume_cap(
        self, oms, account, accounts, pos_shares, volume, expected_sold, desc
    ):
        """卖出同样受成交量 5% 限制"""
        ts_code = "600000.SH"
        account.positions[ts_code] = {"shares": pos_shares, "avg_cost": 10.0, "buy_date": "2026-01-01"}

        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, OrderSide.SELL, 10.0, pos_shares)
        prices = {ts_code: {"close": 10.0, "volume": volume, "prev_close": 10.0}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.traded == expected_sold, f"{desc}: 成交{order.traded} != 期望{expected_sold}"


# ═══════════════════════════════════════════════════════════════
# 3. 滑点参数对成交价的影响
# ═══════════════════════════════════════════════════════════════

class TestSlippage:
    """不同滑点档位下成交价的验证"""

    @pytest.mark.parametrize("slippage, close, desc", [
        (0.0,   10.0,  "零滑点"),
        (0.001, 10.0,  "万分之十(默认)"),
        (0.002, 10.0,  "万分之二十"),
        (0.005, 50.0,  "千分之五_高价股"),
        (0.01,  100.0, "百分之一"),
    ])
    def test_buy_slippage_price(
        self, oms, accounts, slippage, close, desc
    ):
        """买入成交价 = close * (1 + slippage)"""
        matcher = _matcher(oms, slippage=slippage)
        ts_code = "600000.SH"
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": close}}

        matcher.match("2026-01-02", prices, accounts)

        expected_price = close * (1 + slippage)
        trades = oms.get_trades()
        assert len(trades) == 1, f"{desc}: 应有1笔成交"
        assert trades[0].price == pytest.approx(expected_price, rel=1e-9), \
            f"{desc}: 成交价{trades[0].price} != 期望{expected_price}"

    @pytest.mark.parametrize("slippage, close, desc", [
        (0.0,   10.0,  "零滑点"),
        (0.001, 10.0,  "万分之十(默认)"),
        (0.002, 10.0,  "万分之二十"),
        (0.005, 50.0,  "千分之五_高价股"),
        (0.01,  100.0, "百分之一"),
    ])
    def test_sell_slippage_price(
        self, oms, account, accounts, slippage, close, desc
    ):
        """卖出成交价 = close * (1 - slippage)"""
        ts_code = "600000.SH"
        account.positions[ts_code] = {"shares": 1000, "avg_cost": close, "buy_date": "2026-01-01"}

        matcher = _matcher(oms, slippage=slippage)
        order = oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 1000)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": close}}

        matcher.match("2026-01-02", prices, accounts)

        expected_price = close * (1 - slippage)
        trades = oms.get_trades()
        assert len(trades) == 1, f"{desc}: 应有1笔成交"
        assert trades[0].price == pytest.approx(expected_price, rel=1e-9), \
            f"{desc}: 成交价{trades[0].price} != 期望{expected_price}"

    def test_slippage_spread_buy_vs_sell(self, oms, account, accounts):
        """同一收盘价，买入滑点向上、卖出滑点向下，价差 = 2 * slippage * close"""
        slippage = 0.002
        close = 20.0
        ts_code = "600000.SH"
        account.positions[ts_code] = {"shares": 100, "avg_cost": close, "buy_date": "2026-01-01"}

        matcher = _matcher(oms, slippage=slippage)
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": close}}

        # 先卖后买（避免买入更新 buy_date 触发 T+1 拦截卖出）
        oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 100)
        matcher.match("2026-01-02", prices, accounts)
        sell_trade = oms.get_trades()[-1]

        oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        matcher.match("2026-01-02", prices, accounts)
        buy_trade = oms.get_trades()[-1]
        spread = buy_trade.price - sell_trade.price
        expected_spread = 2 * slippage * close

        assert spread == pytest.approx(expected_spread, rel=1e-9)


# ═══════════════════════════════════════════════════════════════
# 4. 连续两个交易日先买后卖 T+1 约束
# ═══════════════════════════════════════════════════════════════

class TestT1Constraint:
    """T+1: 当日买入的股票当日不能卖出，次日可以"""

    @pytest.mark.parametrize("buy_date, sell_date, should_reject, desc", [
        # 同日 → 拒
        ("2026-03-10", "2026-03-10", True,  "同日卖出应拒"),
        # 次日 → 成交
        ("2026-03-10", "2026-03-11", False, "次日卖出应成交"),
        # 隔两日 → 成交
        ("2026-03-10", "2026-03-12", False, "隔两日卖出应成交"),
    ])
    def test_t1_buy_then_sell(
        self, oms, account, accounts, buy_date, sell_date, should_reject, desc
    ):
        ts_code = "600000.SH"
        close = 10.0
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": close}}

        # Day1: 买入
        matcher = _matcher(oms)
        buy_order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        matcher.match(buy_date, prices, accounts)
        assert buy_order.status == OrderStatus.ALLTRADED, f"{desc}: 买入应成交"
        assert account.positions[ts_code]["buy_date"] == buy_date

        # Day2: 尝试卖出
        sell_order = oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 100)
        matcher.match(sell_date, prices, accounts)

        if should_reject:
            assert sell_order.status == OrderStatus.REJECTED, f"{desc}"
            assert "T+1" in sell_order.reject_reason
            assert ts_code in account.positions, f"{desc}: 持仓不应变"
        else:
            assert sell_order.status == OrderStatus.ALLTRADED, f"{desc}"
            assert ts_code not in account.positions, f"{desc}: 持仓应清空"

    def test_t1_buy_date_updated_on_add_position(self, oms, account, accounts):
        """加仓时 buy_date 更新为最新买入日，T+1 以此为准"""
        ts_code = "600000.SH"
        close = 10.0
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": close}}
        matcher = _matcher(oms)

        # Day1: 首次买入
        order1 = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        matcher.match("2026-03-10", prices, accounts)
        assert account.positions[ts_code]["buy_date"] == "2026-03-10"

        # Day2: 加仓 → buy_date 更新为 Day2
        order2 = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        matcher.match("2026-03-11", prices, accounts)
        assert account.positions[ts_code]["buy_date"] == "2026-03-11"
        assert account.positions[ts_code]["shares"] == 200

        # Day2: 同日卖出应被 T+1 拦截（即使首次买入在 Day1）
        sell_order = oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 200)
        matcher.match("2026-03-11", prices, accounts)
        assert sell_order.status == OrderStatus.REJECTED
        assert "T+1" in sell_order.reject_reason

        # Day3: 次日卖出应成功
        sell_order2 = oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 200)
        matcher.match("2026-03-12", prices, accounts)
        assert sell_order2.status == OrderStatus.ALLTRADED

    @pytest.mark.parametrize("ts_code, desc", [
        ("688001.SH", "科创板T+1"),
        ("300001.SZ", "创业板T+1"),
        ("600000.SH", "主板T+1"),
    ])
    def test_t1_applies_across_boards(
        self, oms, account, accounts, ts_code, desc
    ):
        """T+1 在所有板块统一适用"""
        close = 10.0
        prices = {ts_code: {"close": close, "volume": 1_000_000, "prev_close": close}}
        matcher = _matcher(oms)

        buy_order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, close, 100)
        matcher.match("2026-03-10", prices, accounts)
        assert buy_order.status == OrderStatus.ALLTRADED

        sell_order = oms.submit_order("test_strat", ts_code, OrderSide.SELL, close, 100)
        matcher.match("2026-03-10", prices, accounts)
        assert sell_order.status == OrderStatus.REJECTED, f"{desc}: 同日应拒"


# ═══════════════════════════════════════════════════════════════
# 5. 停牌股票（无行情数据）撮合行为
# ═══════════════════════════════════════════════════════════════

class TestSuspension:
    """停牌或无行情时的撮合行为"""

    @pytest.mark.parametrize("side, desc", [
        (OrderSide.BUY,  "停牌股买入"),
        (OrderSide.SELL, "停牌股卖出"),
    ])
    def test_no_market_data_rejected(
        self, oms, account, accounts, side, desc
    ):
        """prices 中不含该股票 → 拒单"""
        ts_code = "600000.SH"
        if side == OrderSide.SELL:
            account.positions[ts_code] = {"shares": 1000, "avg_cost": 10.0, "buy_date": "2026-01-01"}

        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, side, 10.0, 100)
        # prices 不含 600000.SH
        prices = {"000001.SZ": {"close": 20.0, "volume": 500_000, "prev_close": 19.0}}

        matcher.match("2026-01-02", prices, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "无行情" in order.reject_reason

    @pytest.mark.parametrize("side, desc", [
        (OrderSide.BUY,  "空prices买入"),
        (OrderSide.SELL, "空prices卖出"),
    ])
    def test_empty_prices_rejected(
        self, oms, account, accounts, side, desc
    ):
        """prices 为空 → 拒单"""
        ts_code = "600000.SH"
        if side == OrderSide.SELL:
            account.positions[ts_code] = {"shares": 1000, "avg_cost": 10.0, "buy_date": "2026-01-01"}

        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, side, 10.0, 100)

        matcher.match("2026-01-02", {}, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "无行情" in order.reject_reason

    def test_suspension_does_not_affect_other_orders(self, oms, account, accounts):
        """停牌股拒单不影响其他正常股票的撮合"""
        suspended = "600999.SH"
        normal = "600000.SH"

        matcher = _matcher(oms)
        order_suspended = oms.submit_order("test_strat", suspended, OrderSide.BUY, 10.0, 100)
        order_normal = oms.submit_order("test_strat", normal, OrderSide.BUY, 10.0, 100)

        prices = {normal: {"close": 10.0, "volume": 1_000_000, "prev_close": 10.0}}

        matcher.match("2026-01-02", prices, accounts)

        assert order_suspended.status == OrderStatus.REJECTED
        assert order_normal.status == OrderStatus.ALLTRADED

    @pytest.mark.parametrize("ts_code, desc", [
        ("688001.SH", "科创板停牌"),
        ("300001.SZ", "创业板停牌"),
        ("600000.SH", "主板停牌"),
    ])
    def test_suspension_across_boards(
        self, oms, accounts, ts_code, desc
    ):
        """各板块停牌股统一拒单"""
        matcher = _matcher(oms)
        order = oms.submit_order("test_strat", ts_code, OrderSide.BUY, 10.0, 100)

        matcher.match("2026-01-02", {}, accounts)

        assert order.status == OrderStatus.REJECTED, f"{desc}: 应拒单"
        assert "无行情" in order.reject_reason
