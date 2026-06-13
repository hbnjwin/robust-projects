from __future__ import annotations

import numpy as np


def max_drawdown(equity: np.ndarray) -> float:
    peak: float = equity[0]
    max_dd: float = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return float(max_dd)


def annual_return(equity: np.ndarray, days: int = 252) -> float:
    total_return = float(equity[-1] / equity[0] - 1)
    return float((1 + total_return) ** (days / len(equity)) - 1)
