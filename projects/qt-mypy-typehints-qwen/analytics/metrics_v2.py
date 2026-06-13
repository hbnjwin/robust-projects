from __future__ import annotations

from typing import Sequence

import numpy as np


def max_drawdown(equity: np.ndarray) -> float:
    """最大回撤"""
    peak: float = equity[0]
    max_dd: float = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return float(max_dd)


def annual_return(equity: np.ndarray, days: int = 252) -> float:
    """年化收益率"""
    total_return = float(equity[-1] / equity[0] - 1)
    n = len(equity)
    if n <= 1:
        return 0.0
    return float((1 + total_return) ** (days / n) - 1)


def sharpe_ratio(equity: np.ndarray, risk_free: float = 0.03, days: int = 252) -> float:
    """夏普比率"""
    returns = np.diff(equity) / equity[:-1]
    std_val = float(np.std(returns))
    if len(returns) == 0 or std_val == 0:
        return 0.0
    excess = float(np.mean(returns)) - risk_free / days
    return float(excess / std_val * np.sqrt(days))


def sortino_ratio(equity: np.ndarray, risk_free: float = 0.03, days: int = 252) -> float:
    """索提诺比率"""
    returns = np.diff(equity) / equity[:-1]
    if len(returns) == 0:
        return 0.0
    excess = float(np.mean(returns)) - risk_free / days
    downside = returns[returns < 0]
    if len(downside) == 0 or np.std(downside) == 0:
        return float("inf") if excess > 0 else 0.0
    return float(excess / np.std(downside) * np.sqrt(days))


def calmar_ratio(equity: np.ndarray, days: int = 252) -> float:
    """卡尔马比率"""
    ann = annual_return(equity, days)
    mdd = max_drawdown(equity)
    if mdd == 0:
        return float("inf") if ann > 0 else 0.0
    return ann / mdd


def win_rate(trade_returns: Sequence[float]) -> float:
    """胜率"""
    if len(trade_returns) == 0:
        return 0.0
    wins = sum(1 for r in trade_returns if r > 0)
    return wins / len(trade_returns)


def profit_factor(trade_returns: Sequence[float]) -> float:
    """盈亏比"""
    gains = sum(r for r in trade_returns if r > 0)
    losses = abs(sum(r for r in trade_returns if r < 0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def max_consecutive_loss_days(equity: np.ndarray) -> int:
    """最大连续亏损天数"""
    returns = np.diff(equity)
    max_streak = 0
    current = 0
    for r in returns:
        if r < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def turnover_rate(trade_log: list[dict[str, float]], avg_equity: float) -> float:
    """换手率（总成交额/平均权益）"""
    if avg_equity <= 0:
        return 0.0
    total_volume = sum(t.get("price", 0) * t.get("shares", 0) for t in trade_log)
    return float(total_volume / avg_equity)
