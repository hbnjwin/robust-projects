"""metrics_v2 指标计算 -- pytest 风格测试 + 边界参数化."""
import math

import numpy as np
import pytest

from analytics.metrics_v2 import (
    annual_return,
    calmar_ratio,
    max_consecutive_loss_days,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    turnover_rate,
    win_rate,
)


# ── 基本功能测试 ──────────────────────────────────────────────


class TestMaxDrawdown:
    def test_typical(self):
        eq = [100, 110, 105, 95, 100, 90, 95]
        # 峰值110，最低90，回撤 = (110-90)/110 = 0.1818
        assert max_drawdown(eq) == pytest.approx(0.1818, abs=0.01)


class TestAnnualReturn:
    def test_one_year_10pct(self):
        eq = [100_000] * 252 + [110_000]  # 一年后涨10%
        assert annual_return(eq) == pytest.approx(0.10, abs=0.05)


class TestSharpe:
    def test_random_walk(self):
        np.random.seed(42)
        eq = [100_000]
        for _ in range(252):
            eq.append(eq[-1] * (1 + np.random.normal(0.0005, 0.01)))
        result = sharpe_ratio(eq)
        assert isinstance(result, float)
        assert math.isfinite(result)


class TestSortino:
    def test_mostly_up(self):
        eq = [100, 101, 102, 101, 103, 104, 103, 105]
        result = sortino_ratio(eq)
        assert isinstance(result, float)


class TestCalmar:
    def test_uptrend(self):
        eq = [100, 110, 105, 115, 120]
        result = calmar_ratio(eq)
        assert isinstance(result, float)
        assert result > 0


class TestWinRate:
    def test_3_of_5(self):
        trades = [100, -50, 200, -30, 150]
        assert win_rate(trades) == pytest.approx(0.6, abs=0.01)


class TestProfitFactor:
    def test_typical(self):
        trades = [100, -50, 200, -30]
        # gains=300, losses=80 -> 3.75
        assert profit_factor(trades) == pytest.approx(3.75, abs=0.01)


class TestMaxConsecutiveLoss:
    def test_streak_of_3(self):
        eq = [100, 99, 98, 97, 100, 99, 98, 100]
        assert max_consecutive_loss_days(eq) == 3


class TestTurnover:
    def test_two_trades(self):
        log = [
            {"price": 10, "shares": 100},
            {"price": 20, "shares": 200},
        ]
        # (10*100 + 20*200) / 100000 = 5000/100000 = 0.05
        assert turnover_rate(log, 100_000) == pytest.approx(0.05, abs=0.01)


# ── metrics_v2 边界参数化测试 ─────────────────────────────────


class TestEmptySequence:
    """空序列应该抛 IndexError（equity[0] 越界）或返回 0."""

    def test_max_drawdown_empty(self):
        with pytest.raises(IndexError):
            max_drawdown([])

    def test_annual_return_empty(self):
        with pytest.raises(IndexError):
            annual_return([])

    def test_calmar_ratio_empty(self):
        with pytest.raises(IndexError):
            calmar_ratio([])

    def test_sharpe_empty(self):
        assert sharpe_ratio([]) == 0.0

    def test_sortino_empty(self):
        assert sortino_ratio([]) == 0.0

    def test_win_rate_empty(self):
        assert win_rate([]) == 0.0

    def test_profit_factor_empty(self):
        assert profit_factor([]) == 0.0

    def test_max_consecutive_loss_empty(self):
        assert max_consecutive_loss_days([]) == 0

    def test_turnover_empty(self):
        assert turnover_rate([], 100_000) == 0.0


class TestSingleElement:
    """单元素序列 -- 无法计算收益，所有指标应安全返回 0."""

    @pytest.mark.parametrize("fn", [
        max_drawdown,
        annual_return,
        sharpe_ratio,
        sortino_ratio,
        max_consecutive_loss_days,
    ])
    def test_equity_single(self, fn):
        assert fn([100]) == 0.0

    def test_calmar_single(self):
        # ann=0, mdd=0 -> 0.0
        assert calmar_ratio([100]) == 0.0

    def test_win_rate_single_loss(self):
        assert win_rate([-10]) == 0.0

    def test_win_rate_single_win(self):
        assert win_rate([10]) == 1.0

    def test_profit_factor_single_loss(self):
        assert profit_factor([-10]) == 0.0

    def test_profit_factor_single_win(self):
        assert profit_factor([10]) == float("inf")


class TestAllNegativeReturns:
    """全负收益 -- 单调递减 equity, 或全亏交易."""

    _declining = [100, 90, 80, 70]

    def test_max_drawdown_declining(self):
        # (100-70)/100 = 0.30
        assert max_drawdown(self._declining) == pytest.approx(0.30, abs=0.01)

    def test_annual_return_negative(self):
        assert annual_return(self._declining) < 0

    def test_sharpe_negative(self):
        assert sharpe_ratio(self._declining) < 0

    def test_sortino_negative(self):
        assert sortino_ratio(self._declining) < 0

    def test_calmar_negative(self):
        assert calmar_ratio(self._declining) < 0

    def test_consecutive_loss_full(self):
        assert max_consecutive_loss_days(self._declining) == 3

    def test_win_rate_all_losses(self):
        assert win_rate([-10, -20, -30]) == 0.0

    def test_profit_factor_all_losses(self):
        assert profit_factor([-10, -20, -30]) == 0.0


class TestConstantEquity:
    """恒定净值 -- 零波动."""

    _flat = [100, 100, 100, 100]

    def test_max_drawdown_zero(self):
        assert max_drawdown(self._flat) == 0.0

    def test_annual_return_zero(self):
        assert annual_return(self._flat) == 0.0

    def test_sharpe_zero_vol(self):
        assert sharpe_ratio(self._flat) == 0.0

    def test_sortino_zero_vol(self):
        assert sortino_ratio(self._flat) == 0.0

    def test_calmar_zero(self):
        assert calmar_ratio(self._flat) == 0.0

    def test_consecutive_loss_none(self):
        assert max_consecutive_loss_days(self._flat) == 0


class TestAllPositiveReturns:
    """纯盈利 -- mdd=0 时 calmar 应为 inf."""

    _rising = [100, 110, 120, 130]

    def test_max_drawdown_zero(self):
        assert max_drawdown(self._rising) == 0.0

    def test_calmar_inf(self):
        assert calmar_ratio(self._rising) == float("inf")

    def test_win_rate_all_wins(self):
        assert win_rate([10, 20, 30]) == 1.0

    def test_profit_factor_all_wins(self):
        assert profit_factor([10, 20, 30]) == float("inf")


class TestTurnoverEdge:
    def test_zero_equity(self):
        assert turnover_rate([{"price": 10, "shares": 100}], 0) == 0.0

    def test_negative_equity(self):
        assert turnover_rate([{"price": 10, "shares": 100}], -1) == 0.0
