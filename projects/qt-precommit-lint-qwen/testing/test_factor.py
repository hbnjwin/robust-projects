"""测试因子整合模块"""

import sys

sys.path.insert(0, "/home/tulin/quant")
import numpy as np
from factor.factor_analyzer import (
    compute_ic,
    compute_ic_series,
    compute_ir,
    composite_equal_weight,
    composite_ic_weight,
)
from strategies.factor_strategy import FactorStrategy


def test_compute_ic():
    print("=== test_compute_ic ===")
    # 完全正相关
    fv = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0, "E": 5.0}
    fr = {"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04, "E": 0.05}
    ic = compute_ic(fv, fr)
    assert ic is not None
    assert abs(ic - 1.0) < 0.01, "FAIL: ic={:.4f}".format(ic)
    print("  正相关 IC={:.4f} OK".format(ic))

    # 完全负相关
    fr_neg = {"A": 0.05, "B": 0.04, "C": 0.03, "D": 0.02, "E": 0.01}
    ic_neg = compute_ic(fv, fr_neg)
    assert abs(ic_neg - (-1.0)) < 0.01, "FAIL: ic_neg={:.4f}".format(ic_neg)
    print("  负相关 IC={:.4f} OK".format(ic_neg))

    # 不足5只股票
    fv_small = {"A": 1.0, "B": 2.0}
    ic_small = compute_ic(fv_small, fr)
    assert ic_small is None
    print("  不足5只返回None OK")


def test_ic_series_and_ir():
    print("=== test_ic_series_and_ir ===")
    factor_data = {
        "2024-01-01": {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5},
        "2024-01-02": {"A": 2, "B": 1, "C": 4, "D": 3, "E": 5},
        "2024-01-03": {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1},
    }
    return_data = {
        "2024-01-01": {"A": 0.01, "B": 0.02, "C": 0.03, "D": 0.04, "E": 0.05},
        "2024-01-02": {"A": 0.02, "B": 0.01, "C": 0.04, "D": 0.03, "E": 0.05},
        "2024-01-03": {"A": 0.05, "B": 0.04, "C": 0.03, "D": 0.02, "E": 0.01},
    }

    ic_series = compute_ic_series(factor_data, return_data)
    assert len(ic_series) == 3
    print("  IC序列长度={} OK".format(len(ic_series)))

    ir = compute_ir(ic_series)
    print("  IR={:.4f} OK".format(ir))


def test_composite_equal():
    print("=== test_composite_equal ===")
    f1 = {"2024-01-01": {"A": 1.0, "B": 2.0}}
    f2 = {"2024-01-01": {"A": 3.0, "B": 4.0}}

    result = composite_equal_weight([f1, f2])
    assert abs(result["2024-01-01"]["A"] - 2.0) < 0.01
    assert abs(result["2024-01-01"]["B"] - 3.0) < 0.01
    print("  等权合成 OK")


def test_composite_ic():
    print("=== test_composite_ic ===")
    f1 = {"2024-01-01": {"A": 1.0, "B": 2.0}}
    f2 = {"2024-01-01": {"A": 3.0, "B": 4.0}}

    result = composite_ic_weight([f1, f2], [0.1, 0.3])
    # weights: 0.1/0.4=0.25, 0.3/0.4=0.75
    expected_a = 1.0 * 0.25 + 3.0 * 0.75  # 2.5
    assert abs(result["2024-01-01"]["A"] - expected_a) < 0.01
    print("  IC加权合成 A={:.2f} OK".format(result["2024-01-01"]["A"]))


def test_factor_strategy():
    print("=== test_factor_strategy ===")
    scores = {"2024-01-01": {"A": 5.0, "B": 4.0, "C": 3.0, "D": 2.0, "E": 1.0, "F": 0.5, "G": 0.3, "H": 0.1}}
    prices = {
        "A": {"close": 10},
        "B": {"close": 20},
        "C": {"close": 15},
        "D": {"close": 12},
        "E": {"close": 8},
        "F": {"close": 5},
        "G": {"close": 3},
        "H": {"close": 2},
    }

    strategy = FactorStrategy(scores, top_n=3, rebalance_days=20)
    signals = strategy.generate("2024-01-01", prices)

    buy_codes = set(s["ts_code"] for s in signals if s["action"] == "buy")
    assert buy_codes == {"A", "B", "C"}, "FAIL: {}".format(buy_codes)
    print("  选股: {} OK".format(buy_codes))

    # 验证 weight
    for s in signals:
        if s["action"] == "buy":
            assert abs(s["weight"] - 1.0 / 3) < 0.01
    print("  等权weight OK")

    # 非调仓日
    signals2 = strategy.generate("2024-01-02", prices)
    assert len(signals2) == 0
    print("  非调仓日无信号 OK")


if __name__ == "__main__":
    test_compute_ic()
    test_ic_series_and_ir()
    test_composite_equal()
    test_composite_ic()
    test_factor_strategy()
    print("\n" + "=" * 50)
    print("因子整合测试全部通过")
