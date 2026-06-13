"""
factor_lib/ts_factors.py — 时序因子函数库

基于 pandas/numpy，补充 SQL 难以表达的时序因子。
所有函数接受 pd.Series（单股票时序），返回 pd.Series。
命名与 vnpy Alpha158 对齐，方便对比和复用。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ── 基础时序算子 ─────────────────────────────────────────────

def ts_delay(s: pd.Series, n: int) -> pd.Series:
    """N 日前的值"""
    return s.shift(n)


def ts_delta(s: pd.Series, n: int) -> pd.Series:
    """N 日变化量"""
    return s - s.shift(n)


def ts_pct(s: pd.Series, n: int) -> pd.Series:
    """N 日收益率"""
    return s / s.shift(n) - 1


def ts_mean(s: pd.Series, n: int) -> pd.Series:
    """N 日滚动均值"""
    return s.rolling(n, min_periods=1).mean()


def ts_std(s: pd.Series, n: int) -> pd.Series:
    """N 日滚动标准差"""
    return s.rolling(n, min_periods=2).std()


def ts_min(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=1).min()


def ts_max(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=1).max()


def ts_sum(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=1).sum()


def ts_rank(s: pd.Series, n: int) -> pd.Series:
    """N 日窗口内的时序排名（百分位）"""
    return s.rolling(n, min_periods=1).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )


def ts_argmax(s: pd.Series, n: int) -> pd.Series:
    """N 日窗口内最大值的位置（从1开始）"""
    return s.rolling(n, min_periods=1).apply(
        lambda x: int(np.argmax(x)) + 1, raw=True
    )


def ts_argmin(s: pd.Series, n: int) -> pd.Series:
    """N 日窗口内最小值的位置（从1开始）"""
    return s.rolling(n, min_periods=1).apply(
        lambda x: int(np.argmin(x)) + 1, raw=True
    )


def ts_corr(s1: pd.Series, s2: pd.Series, n: int) -> pd.Series:
    """N 日滚动相关系数"""
    return s1.rolling(n, min_periods=2).corr(s2)


def ts_cov(s1: pd.Series, s2: pd.Series, n: int) -> pd.Series:
    """N 日滚动协方差"""
    return s1.rolling(n, min_periods=2).cov(s2)


def ts_slope(s: pd.Series, n: int) -> pd.Series:
    """N 日线性回归斜率（beta）"""
    def _slope(x):
        if len(x) < 2:
            return np.nan
        t = np.arange(len(x))
        slope, _, _, _, _ = stats.linregress(t, x)
        return slope
    return s.rolling(n, min_periods=2).apply(_slope, raw=True)


def ts_rsquare(s: pd.Series, n: int) -> pd.Series:
    """N 日线性回归 R²"""
    def _r2(x):
        if len(x) < 2:
            return np.nan
        t = np.arange(len(x))
        _, _, r, _, _ = stats.linregress(t, x)
        return r ** 2
    return s.rolling(n, min_periods=2).apply(_r2, raw=True)


def ts_resi(s: pd.Series, n: int) -> pd.Series:
    """N 日线性回归残差（最后一个点）"""
    def _resi(x):
        if len(x) < 2:
            return np.nan
        t = np.arange(len(x))
        slope, intercept, _, _, _ = stats.linregress(t, x)
        return x[-1] - (slope * (len(x) - 1) + intercept)
    return s.rolling(n, min_periods=2).apply(_resi, raw=True)


def ts_quantile(s: pd.Series, n: int, q: float) -> pd.Series:
    """N 日滚动分位数"""
    return s.rolling(n, min_periods=1).quantile(q)


def ts_zscore(s: pd.Series, n: int) -> pd.Series:
    """N 日 Z-Score 标准化"""
    mu  = ts_mean(s, n)
    std = ts_std(s, n)
    return (s - mu) / std.replace(0, np.nan)


# ── 技术指标因子 ─────────────────────────────────────────────

def factor_rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI 相对强弱指数"""
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(n, min_periods=1).mean()
    loss  = (-delta.clip(upper=0)).rolling(n, min_periods=1).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def factor_macd_diff(close: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    """MACD DIF（快线 - 慢线）"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    return ema_fast - ema_slow


def factor_macd_hist(close: pd.Series, fast=12, slow=26, signal=9) -> pd.Series:
    """MACD 柱状图（DIF - DEA）"""
    dif = factor_macd_diff(close, fast, slow, signal)
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif - dea


def factor_boll_pos(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.Series:
    """布林带位置：(close - 下轨) / (上轨 - 下轨)，范围 [0,1]"""
    mid  = ts_mean(close, n)
    std  = ts_std(close, n)
    upper = mid + k * std
    lower = mid - k * std
    band  = (upper - lower).replace(0, np.nan)
    return (close - lower) / band


def factor_atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    """ATR 真实波幅"""
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=1).mean()


def factor_turnover(volume: pd.Series, float_shares: pd.Series) -> pd.Series:
    """换手率 = 成交量 / 流通股本"""
    return volume / float_shares.replace(0, np.nan)


# ── Alpha101 精选因子（SQL 难以表达的部分）────────────────────

def alpha_001(returns: pd.Series, close: pd.Series, n: int = 20) -> pd.Series:
    """
    Alpha#1: rank(argmax(pow(ifelse(returns < 0, std(returns, n), close), 2), 5)) - 0.5
    简化版：5日最大收益位置的截面排名
    """
    cond = returns < 0
    x = pd.Series(np.where(cond, ts_std(returns, n), close), index=returns.index)
    return ts_argmax(x ** 2, 5)


def alpha_006(open_: pd.Series, volume: pd.Series, n: int = 10) -> pd.Series:
    """Alpha#6: -1 * corr(open, volume, 10)"""
    return -ts_corr(open_, volume, n)


def alpha_013(close: pd.Series, volume: pd.Series, n: int = 5) -> pd.Series:
    """Alpha#13: -1 * rank(cov(rank(close), rank(volume), 5))"""
    r_close  = close.rank(pct=True)
    r_volume = volume.rank(pct=True)
    return -ts_cov(r_close, r_volume, n)


def alpha_016(high: pd.Series, volume: pd.Series, n: int = 5) -> pd.Series:
    """Alpha#16: -1 * rank(cov(rank(high), rank(volume), 5))"""
    r_high   = high.rank(pct=True)
    r_volume = volume.rank(pct=True)
    return -ts_cov(r_high, r_volume, n)


def alpha_028(close: pd.Series, high: pd.Series, low: pd.Series,
              volume: pd.Series) -> pd.Series:
    """
    Alpha#28: scale(corr(adv20, low, 5) + (high + low) / 2 - close)
    adv20 = 20日均量
    """
    adv20 = ts_mean(volume, 20)
    corr  = ts_corr(adv20, low, 5)
    raw   = corr + (high + low) / 2 - close
    # scale: 除以截面绝对值之和
    abs_sum = raw.abs().sum()
    return raw / abs_sum if abs_sum > 0 else raw
