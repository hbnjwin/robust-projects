"""测试架构统一：metrics_v2 指标计算（pytest 版）"""
import numpy as np
import pytest

from analytics.metrics_v2 import (
    max_drawdown,
    annual_return,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    win_rate,
    profit_factor,
    max_consecutive_loss_days,
    turnover_rate,
)


# ═══════════════════════════════════════════════════════════════════════════
# Original tests (converted from print+assert to pytest style)
# ═══════════════════════════════════════════════════════════════════════════

class TestMaxDrawdown:
    def test_typical(self):
        eq = [100, 110, 105, 95, 100, 90, 95]
        dd = max_drawdown(eq)
        # 峰值110，最低90，回撤 = (110-90)/110 ≈ 0.1818
        assert dd == pytest.approx(0.1818, abs=0.01)

    def test_known_value(self):
        # peak=200, trough=100 → dd=0.5
        assert max_drawdown([100, 200, 150, 100, 180]) == pytest.approx(0.5)


class TestAnnualReturn:
    def test_one_year_10pct(self):
        eq = [100_000] * 252 + [110_000]  # 一年后涨10%
        ar = annual_return(eq)
        assert ar == pytest.approx(0.10, abs=0.05)


class TestSharpe:
    def test_positive_drift(self):
        np.random.seed(42)
        eq = [100_000]
        for _ in range(252):
            eq.append(eq[-1] * (1 + np.random.normal(0.0005, 0.01)))
        s = sharpe_ratio(eq)
        # With positive drift the Sharpe should be > 0
        assert s > 0


class TestSortino:
    def test_basic(self):
        eq = [100, 101, 102, 101, 103, 104, 103, 105]
        s = sortino_ratio(eq)
        assert isinstance(s, float)


class TestCalmar:
    def test_basic(self):
        eq = [100, 110, 105, 115, 120]
        c = calmar_ratio(eq)
        assert isinstance(c, float)
        assert c > 0  # positive return → positive calmar


class TestWinRate:
    def test_mixed(self):
        trades = [100, -50, 200, -30, 150]
        wr = win_rate(trades)
        assert wr == pytest.approx(0.6, abs=0.01)


class TestProfitFactor:
    def test_mixed(self):
        trades = [100, -50, 200, -30]
        pf = profit_factor(trades)
        assert pf == pytest.approx(3.75, abs=0.01)


class TestMaxConsecutiveLoss:
    def test_three_streak(self):
        eq = [100, 99, 98, 97, 100, 99, 98, 100]
        mcl = max_consecutive_loss_days(eq)
        assert mcl == 3


class TestTurnover:
    def test_basic(self):
        log = [
            {"price": 10, "shares": 100},
            {"price": 20, "shares": 200},
        ]
        tr = turnover_rate(log, 100_000)
        # total_volume = 10*100 + 20*200 = 5000,  5000/100000 = 0.05
        assert tr == pytest.approx(0.05, abs=0.01)


# ═══════════════════════════════════════════════════════════════════════════
# Parameterized edge-case tests for metrics_v2
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界情况参数化测试"""

    # ---- max_drawdown ----------------------------------------------------

    @pytest.mark.parametrize("equity, expected", [
        ([100],              0.0),        # 单元素 — 无回撤
        ([100, 100, 100],    0.0),        # 恒定 — 无回撤
        ([100, 200, 300],    0.0),        # 单调递增 — 无回撤
        ([300, 200, 100],    pytest.approx(2/3)),  # 单调递减 — 最大回撤
        ([100, 50, 100, 50], pytest.approx(0.5)),  # 多次相同回撤
    ])
    def test_max_drawdown(self, equity, expected):
        assert max_drawdown(equity) == expected

    def test_max_drawdown_empty_raises(self):
        """空序列当前会抛出 IndexError（已知行为）"""
        with pytest.raises(IndexError):
            max_drawdown([])

    # ---- annual_return ---------------------------------------------------

    @pytest.mark.parametrize("equity, days, expected", [
        # 253 点（≈1 年交易日），收益 10% → 年化 ≈ 10%
        ([100_000] * 252 + [110_000],  252, pytest.approx(0.10, abs=0.01)),
        # 零收益
        ([100, 100],                   252, pytest.approx(0.0)),
        # 亏损 50%（2 点，年化 = 0.5^252 - 1 ≈ -1.0）
        ([100, 50],                    252, pytest.approx(-1.0, abs=0.01)),
        # 单元素 → 0.0（n <= 1 guard）
        ([100],                        252, 0.0),
        # 翻番（253 点，年化 ≈ 100%）
        ([100_000] * 252 + [200_000],  252, pytest.approx(1.0, abs=0.05)),
    ])
    def test_annual_return(self, equity, days, expected):
        assert annual_return(equity, days) == expected

    def test_annual_return_empty_raises(self):
        """空序列当前会抛出 IndexError（已知行为）"""
        with pytest.raises(IndexError):
            annual_return([])

    # ---- sharpe_ratio ----------------------------------------------------

    @pytest.mark.parametrize("equity, description", [
        ([100],                   "单元素 → 0.0"),
        ([100, 100, 100, 100],    "恒定序列（零标准差）→ 0.0"),
    ])
    def test_sharpe_degenerate(self, equity, description):
        assert sharpe_ratio(equity) == 0.0

    def test_sharpe_empty(self):
        """空序列 → 0.0（函数内部 guard）"""
        assert sharpe_ratio([]) == 0.0

    def test_sharpe_all_negative_returns(self):
        """全负收益 → Sharpe < 0"""
        eq = [100, 99, 98, 97, 96, 95]
        assert sharpe_ratio(eq) < 0

    # ---- sortino_ratio ---------------------------------------------------

    @pytest.mark.parametrize("equity, expected_type", [
        ([100, 101, 102, 103, 104],  float),   # 全正收益 → inf or positive
        ([100, 100, 100, 100],       float),   # 恒定 → 0.0
    ])
    def test_sortino_degenerate(self, equity, expected_type):
        result = sortino_ratio(equity)
        assert isinstance(result, expected_type)

    def test_sortino_all_positive_returns_is_inf(self):
        """全正收益且 excess > 0 → inf"""
        eq = [100, 102, 104, 106, 108]  # strong positive drift
        assert sortino_ratio(eq, risk_free=0.0) == float("inf")

    def test_sortino_empty(self):
        assert sortino_ratio([]) == 0.0

    # ---- calmar_ratio ----------------------------------------------------

    def test_calmar_no_drawdown_positive_return(self):
        """无回撤 + 正收益 → inf"""
        eq = [100, 101, 102, 103]
        assert calmar_ratio(eq) == float("inf")

    def test_calmar_no_drawdown_zero_return(self):
        """无回撤 + 零收益 → 0.0"""
        eq = [100, 100, 100]
        assert calmar_ratio(eq) == 0.0

    # ---- win_rate --------------------------------------------------------

    @pytest.mark.parametrize("trades, expected", [
        ([],                     0.0),          # 空列表
        ([1, 2, 3],             1.0),           # 全赢
        ([-1, -2, -3],          0.0),           # 全输
        ([0, 0, 0],             0.0),           # 全平 (r > 0 才算赢)
        ([1, -1],               0.5),           # 50/50
        ([1, -1, 1, -1, 1],    0.6),           # 3赢2输
    ])
    def test_win_rate(self, trades, expected):
        assert win_rate(trades) == pytest.approx(expected)

    # ---- profit_factor ---------------------------------------------------

    @pytest.mark.parametrize("trades, expected", [
        ([],               0.0),                # 空列表 → 0.0
        ([1, 2, 3],        float("inf")),       # 全赢无亏 → inf
        ([-1, -2, -3],     0.0),                # 全输 → 0.0
        ([100, -100],      pytest.approx(1.0)), # 盈亏平衡 → 1.0
        ([200, -100],      pytest.approx(2.0)), # 2:1
        ([0, 0, 0],        0.0),                # 全平 → 0.0
    ])
    def test_profit_factor(self, trades, expected):
        assert profit_factor(trades) == expected

    # ---- max_consecutive_loss_days ---------------------------------------

    @pytest.mark.parametrize("equity, expected", [
        ([100],                         0),   # 单元素
        ([100, 100, 100],               0),   # 恒定
        ([100, 101, 102, 103],          0),   # 单调增
        ([100, 99, 98, 97, 100],        3),   # 3连跌
        ([100, 99, 100, 99, 98, 97],    3),   # 中间回升后再跌3天
        ([100, 99, 98, 100, 99, 98, 97, 96], 4),  # 最长4连跌
    ])
    def test_max_consecutive_loss_days(self, equity, expected):
        assert max_consecutive_loss_days(equity) == expected

    def test_max_consecutive_loss_days_empty(self):
        """空序列 → 0"""
        assert max_consecutive_loss_days([]) == 0

    # ---- turnover_rate ---------------------------------------------------

    @pytest.mark.parametrize("trade_log, avg_equity, expected", [
        ([],                        100_000,  0.0),       # 无交易
        ([{"price": 10, "shares": 100}], 0,   0.0),       # 权益为 0 → 0.0
        ([{"price": 10, "shares": 100}], -1,  0.0),       # 负权益 → 0.0
        ([{"price": 0, "shares": 100}],  100, 0.0),       # 价格为 0
        ([{"price": 10, "shares": 0}],   100, 0.0),       # 股数为 0
        ([{"price": 10, "shares": 100},
          {"price": 20, "shares": 200}], 100_000,
         pytest.approx(0.05, abs=0.001)),                  # 标准场景
    ])
    def test_turnover_rate(self, trade_log, avg_equity, expected):
        assert turnover_rate(trade_log, avg_equity) == expected
