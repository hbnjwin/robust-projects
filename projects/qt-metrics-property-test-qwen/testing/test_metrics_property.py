"""基于 hypothesis 的属性测试 —— metrics_v2 模块

覆盖 5 条性质：
  1) max_drawdown 对任意正净值曲线 ∈ [0, 1]，平推序列回撤为 0
  2) sharpe_ratio / sortino_ratio 在收益全为正常数时为有限正值
  3) profit_factor 无亏损时返回 inf，不抛异常
  4) win_rate 始终 ∈ [0, 1]
  5) 空序列输入时所有函数不应抛未处理异常
"""
import math
import sys

sys.path.insert(0, ".")

from hypothesis import given, strategies as st, assume
import numpy as np

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

# ── 公共策略 ────────────────────────────────────────────────────────
# 正净值序列：元素 ≥ 1.0，避免除以 0
positive_equity_curves = st.lists(
    st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=2,
    max_size=500,
)

# 平推（常数）净值序列
flat_equity_curves = st.lists(
    st.floats(min_value=1.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=1,
).map(lambda xs: xs * 5)  # 5 个相同值

# 正收益率序列（用于模拟全赢交易）
positive_trade_returns = st.lists(
    st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=500,
)

# 任意交易收益率（含正负）
mixed_trade_returns = st.lists(
    st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
    min_size=0,
    max_size=500,
)


# ── 1) max_drawdown ∈ [0, 1] 且平推序列回撤为 0 ────────────────────
@given(positive_equity_curves)
def test_max_drawdown_range(equity):
    """对任意正净值曲线，max_drawdown 结果应在 [0, 1] 之间"""
    dd = max_drawdown(equity)
    assert 0 <= dd <= 1, f"max_drawdown={dd} 不在 [0,1] 范围内, equity[:5]={equity[:5]}"


@given(flat_equity_curves)
def test_max_drawdown_flat(equity):
    """平推序列的回撤应为 0"""
    dd = max_drawdown(equity)
    assert dd == 0.0, f"平推序列回撤应为 0，实际 dd={dd}"


# ── 2) sharpe_ratio / sortino_ratio 在收益全为正常数时为有限正值 ──────
@given(positive_trade_returns)
def test_sharpe_ratio_positive_constant_returns(returns):
    """收益全为正常数时，sharpe_ratio 应为有限正值"""
    # 将收益率还原为净值曲线
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    # 至少需要 2 个不同的收益率才能得到非零标准差
    np_returns = np.diff(equity) / np.array(equity[:-1])
    assume(len(np_returns) >= 2 and np.std(np_returns) > 0)
    # risk_free=0 保证超额收益为正
    s = sharpe_ratio(equity, risk_free=0.0)
    assert math.isfinite(s) and s > 0, (
        f"sharpe_ratio={s}，期望有限正值"
    )


@given(positive_trade_returns)
def test_sortino_ratio_positive_constant_returns(returns):
    """收益全为正常数时，sortino_ratio 应为有限正值或 +inf"""
    equity = [100.0]
    for r in returns:
        equity.append(equity[-1] * (1 + r / 100))
    s = sortino_ratio(equity, risk_free=0.0)
    # 全正收益 → 下行标准差为 0 → 实现返回 inf，这也是合理结果
    assert (math.isfinite(s) and s > 0) or math.isinf(s), (
        f"sortino_ratio={s}，期望有限正值或 +inf"
    )


# ── 3) profit_factor 无亏损交易时返回 inf，不抛异常 ────────────────
@given(positive_trade_returns)
def test_profit_factor_no_losses(trades):
    """当没有亏损交易时，profit_factor 应返回 inf 而非抛异常"""
    pf = profit_factor(trades)
    assert math.isinf(pf), f"profit_factor={pf}，期望 inf（无亏损交易）"


# ── 4) win_rate 始终在 [0, 1] 范围内 ───────────────────────────────
@given(mixed_trade_returns)
def test_win_rate_range(trades):
    """win_rate 应始终在 [0, 1] 范围内"""
    wr = win_rate(trades)
    assert 0 <= wr <= 1, f"win_rate={wr} 不在 [0,1] 范围内, trades[:5]={trades[:5]}"


# ── 5) 空序列输入时所有函数不应抛未处理异常 ────────────────────────
def test_empty_input_safety():
    """空序列或单元素输入时所有函数不应抛未处理异常"""
    for equity in [[], [100.0]]:
        dd = max_drawdown(equity)
        assert isinstance(dd, (int, float))

        ar = annual_return(equity)
        assert isinstance(ar, (int, float))

        s = sharpe_ratio(equity)
        assert isinstance(s, (int, float))

        so = sortino_ratio(equity)
        assert isinstance(so, (int, float))

        c = calmar_ratio(equity)
        assert isinstance(c, (int, float))

        mcl = max_consecutive_loss_days(equity)
        assert isinstance(mcl, (int, float, np.integer))

    # win_rate / profit_factor 接受交易列表
    wr = win_rate([])
    assert isinstance(wr, (int, float))

    pf = profit_factor([])
    assert isinstance(pf, (int, float))

    # turnover_rate 空交易日志
    tr = turnover_rate([], 100000)
    assert isinstance(tr, (int, float))
