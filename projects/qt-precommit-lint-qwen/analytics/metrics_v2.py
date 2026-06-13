import numpy as np


def max_drawdown(equity):
    """最大回撤"""
    peak = equity[0]
    max_dd = 0
    for v in equity:
        peak = max(peak, v)
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)
    return max_dd


def annual_return(equity, days=252):
    """年化收益率"""
    total_return = equity[-1] / equity[0] - 1
    n = len(equity)
    if n <= 1:
        return 0.0
    return (1 + total_return) ** (days / n) - 1


def sharpe_ratio(equity, risk_free=0.03, days=252):
    """夏普比率"""
    returns = np.diff(equity) / equity[:-1]
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0
    excess = np.mean(returns) - risk_free / days
    return excess / np.std(returns) * np.sqrt(days)


def sortino_ratio(equity, risk_free=0.03, days=252):
    """索提诺比率"""
    returns = np.diff(equity) / equity[:-1]
    if len(returns) == 0:
        return 0.0
    excess = np.mean(returns) - risk_free / days
    downside = returns[returns < 0]
    if len(downside) == 0 or np.std(downside) == 0:
        return float("inf") if excess > 0 else 0.0
    return excess / np.std(downside) * np.sqrt(days)


def calmar_ratio(equity, days=252):
    """卡尔马比率"""
    ann = annual_return(equity, days)
    mdd = max_drawdown(equity)
    if mdd == 0:
        return float("inf") if ann > 0 else 0.0
    return ann / mdd


def win_rate(trade_returns):
    """胜率"""
    if len(trade_returns) == 0:
        return 0.0
    wins = sum(1 for r in trade_returns if r > 0)
    return wins / len(trade_returns)


def profit_factor(trade_returns):
    """盈亏比"""
    gains = sum(r for r in trade_returns if r > 0)
    losses = abs(sum(r for r in trade_returns if r < 0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def max_consecutive_loss_days(equity):
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


def turnover_rate(trade_log, avg_equity):
    """换手率（总成交额/平均权益）"""
    if avg_equity <= 0:
        return 0.0
    total_volume = sum(t.get("price", 0) * t.get("shares", 0) for t in trade_log)
    return total_volume / avg_equity
