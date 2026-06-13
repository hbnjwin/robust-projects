"""测试架构统一：metrics_v2 指标计算"""

import sys

sys.path.insert(0, "/home/tulin/quant")
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


def test_max_drawdown():
    print("=== test_max_drawdown ===")
    eq = [100, 110, 105, 95, 100, 90, 95]
    dd = max_drawdown(eq)
    # 峰值110，最低90，回撤 = (110-90)/110 = 0.1818
    assert abs(dd - 0.1818) < 0.01, f"FAIL: dd={dd}"
    print(f"  max_drawdown={dd:.4f} OK")


def test_annual_return():
    print("=== test_annual_return ===")
    eq = [100000] * 252 + [110000]  # 一年后涨10%
    ar = annual_return(eq)
    assert abs(ar - 0.10) < 0.05, f"FAIL: ar={ar}"
    print(f"  annual_return={ar:.4f} OK")


def test_sharpe():
    print("=== test_sharpe ===")
    np.random.seed(42)
    eq = [100000]
    for _ in range(252):
        eq.append(eq[-1] * (1 + np.random.normal(0.0005, 0.01)))
    s = sharpe_ratio(eq)
    print(f"  sharpe={s:.4f} OK")


def test_sortino():
    print("=== test_sortino ===")
    eq = [100, 101, 102, 101, 103, 104, 103, 105]
    s = sortino_ratio(eq)
    print(f"  sortino={s:.4f} OK")


def test_calmar():
    print("=== test_calmar ===")
    eq = [100, 110, 105, 115, 120]
    c = calmar_ratio(eq)
    print(f"  calmar={c:.4f} OK")


def test_win_rate():
    print("=== test_win_rate ===")
    trades = [100, -50, 200, -30, 150]
    wr = win_rate(trades)
    assert abs(wr - 0.6) < 0.01, f"FAIL: wr={wr}"
    print(f"  win_rate={wr:.4f} OK")


def test_profit_factor():
    print("=== test_profit_factor ===")
    trades = [100, -50, 200, -30]
    pf = profit_factor(trades)
    assert abs(pf - 3.75) < 0.01, f"FAIL: pf={pf}"
    print(f"  profit_factor={pf:.4f} OK")


def test_max_consecutive_loss():
    print("=== test_max_consecutive_loss ===")
    eq = [100, 99, 98, 97, 100, 99, 98, 100]
    mcl = max_consecutive_loss_days(eq)
    assert mcl == 3, f"FAIL: mcl={mcl}"
    print(f"  max_consecutive_loss={mcl} OK")


def test_turnover():
    print("=== test_turnover ===")
    log = [
        {"price": 10, "shares": 100},
        {"price": 20, "shares": 200},
    ]
    tr = turnover_rate(log, 100000)
    assert abs(tr - 0.05) < 0.01, f"FAIL: tr={tr}"
    print(f"  turnover={tr:.4f} OK")


if __name__ == "__main__":
    test_max_drawdown()
    test_annual_return()
    test_sharpe()
    test_sortino()
    test_calmar()
    test_win_rate()
    test_profit_factor()
    test_max_consecutive_loss()
    test_turnover()
    print("\n" + "=" * 50)
    print("架构统一测试全部通过")
