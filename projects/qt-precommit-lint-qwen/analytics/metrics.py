import numpy as np


def max_drawdown(equity):
    peak = equity[0]
    max_dd = 0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return max_dd


def annual_return(equity, days=252):
    total_return = equity[-1] / equity[0] - 1
    return (1 + total_return) ** (days / len(equity)) - 1
