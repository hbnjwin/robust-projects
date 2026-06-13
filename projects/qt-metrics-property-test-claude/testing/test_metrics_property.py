"""Property-based tests for analytics.metrics_v2 using Hypothesis."""
import math
import numpy as np
import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

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

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Positive equity curve: at least 2 points, values in a safe positive range
equity_curve = st.lists(
    st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=500,
)

# Trade returns: finite floats in a bounded range
trade_returns_st = st.lists(
    st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=500,
)

# Positive-only trade returns (no losses)
positive_returns_st = st.lists(
    st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=200,
)


@st.composite
def monotonic_increasing_equity(draw):
    """Generate a strictly increasing equity curve with all-positive daily returns.

    Each daily return is between 0.05% and 2%, guaranteeing mean return
    well above risk_free / days ≈ 0.012%.
    """
    start = draw(st.floats(min_value=100.0, max_value=1e5,
                           allow_nan=False, allow_infinity=False))
    length = draw(st.integers(min_value=10, max_value=300))
    daily_returns = draw(
        st.lists(
            st.floats(min_value=0.0005, max_value=0.02,
                      allow_nan=False, allow_infinity=False),
            min_size=length,
            max_size=length,
        )
    )
    eq = [start]
    for r in daily_returns:
        eq.append(eq[-1] * (1 + r))
    return eq


# ---------------------------------------------------------------------------
# 1) max_drawdown: result in [0, 1]; flat series → 0
# ---------------------------------------------------------------------------

class TestMaxDrawdown:
    @given(eq=equity_curve)
    def test_bounded_zero_one(self, eq):
        dd = max_drawdown(eq)
        assert 0 <= dd <= 1, f"max_drawdown out of range: {dd}"

    @given(val=st.floats(min_value=1.0, max_value=1e6,
                         allow_nan=False, allow_infinity=False),
           n=st.integers(min_value=2, max_value=500))
    def test_flat_series_zero(self, val, n):
        eq = [val] * n
        assert max_drawdown(eq) == 0.0


# ---------------------------------------------------------------------------
# 2) sharpe_ratio / sortino_ratio: positive with all-positive returns
# ---------------------------------------------------------------------------

class TestSharpePositiveReturns:
    @given(eq=monotonic_increasing_equity())
    def test_finite_positive(self, eq):
        s = sharpe_ratio(eq)
        assert math.isfinite(s), f"sharpe not finite: {s}"
        assert s > 0, f"sharpe not positive: {s}"


class TestSortinoPositiveReturns:
    @given(eq=monotonic_increasing_equity())
    def test_positive(self, eq):
        """sortino should be positive (may be inf when there's no downside)."""
        s = sortino_ratio(eq)
        assert s > 0, f"sortino not positive: {s}"
        # inf is acceptable (no downside deviation), but NaN is not
        assert not math.isnan(s), f"sortino is NaN"


# ---------------------------------------------------------------------------
# 3) profit_factor: no losses → inf (not exception)
# ---------------------------------------------------------------------------

class TestProfitFactor:
    @given(returns=positive_returns_st)
    def test_no_loss_returns_inf(self, returns):
        pf = profit_factor(returns)
        assert pf == float('inf'), f"Expected inf, got {pf}"

    @given(returns=trade_returns_st)
    def test_non_negative(self, returns):
        pf = profit_factor(returns)
        assert pf >= 0, f"profit_factor negative: {pf}"


# ---------------------------------------------------------------------------
# 4) win_rate: always in [0, 1]
# ---------------------------------------------------------------------------

class TestWinRate:
    @given(returns=trade_returns_st)
    def test_bounded_zero_one(self, returns):
        wr = win_rate(returns)
        assert 0 <= wr <= 1, f"win_rate out of range: {wr}"

    @given(returns=positive_returns_st)
    def test_all_wins(self, returns):
        assert win_rate(returns) == 1.0


# ---------------------------------------------------------------------------
# 5) Empty-sequence safety: should not raise unhandled exceptions
# ---------------------------------------------------------------------------

_EQUITY_FUNCS = {
    "max_drawdown": max_drawdown,
    "annual_return": annual_return,
    "sharpe_ratio": sharpe_ratio,
    "sortino_ratio": sortino_ratio,
    "calmar_ratio": calmar_ratio,
    "max_consecutive_loss_days": max_consecutive_loss_days,
}

_TRADE_FUNCS = {
    "win_rate": win_rate,
    "profit_factor": profit_factor,
}


class TestEmptyInput:
    @pytest.mark.parametrize("name,fn", list(_EQUITY_FUNCS.items()))
    def test_equity_empty(self, name, fn):
        """No equity-based function should raise on empty input."""
        try:
            fn([])
        except Exception as exc:
            pytest.fail(f"{name}([]) raised {type(exc).__name__}: {exc}")

    @pytest.mark.parametrize("name,fn", list(_TRADE_FUNCS.items()))
    def test_trade_empty(self, name, fn):
        """No trade-returns function should raise on empty input."""
        try:
            fn([])
        except Exception as exc:
            pytest.fail(f"{name}([]) raised {type(exc).__name__}: {exc}")

    def test_turnover_empty(self):
        try:
            turnover_rate([], 100000)
        except Exception as exc:
            pytest.fail(f"turnover_rate([], ...) raised {type(exc).__name__}: {exc}")
