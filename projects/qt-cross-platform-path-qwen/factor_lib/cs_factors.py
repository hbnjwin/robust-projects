"""
factor_lib/cs_factors.py — 截面因子函数库

基于 pandas，对每个截面日期做跨股票操作。
所有函数接受 pd.Series（单日截面，index=ts_code），返回 pd.Series。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def cs_rank(s: pd.Series) -> pd.Series:
    """截面排名（百分位，0~1）"""
    return s.rank(pct=True)


def cs_zscore(s: pd.Series) -> pd.Series:
    """截面 Z-Score 标准化"""
    mu  = s.mean()
    std = s.std()
    return (s - mu) / std if std > 0 else pd.Series(0.0, index=s.index)


def cs_robust_zscore(s: pd.Series) -> pd.Series:
    """截面 Robust Z-Score: (x - median) / (MAD * 1.4826)，clip[-3,3]"""
    med = s.median()
    mad = (s - med).abs().median()
    if mad == 0:
        return pd.Series(0.0, index=s.index)
    z = (s - med) / (mad * 1.4826)
    return z.clip(-3, 3)


def cs_winsorize(s: pd.Series, q: float = 0.01) -> pd.Series:
    """截面去极值（上下各 q 分位数截断）"""
    lo = s.quantile(q)
    hi = s.quantile(1 - q)
    return s.clip(lo, hi)


def cs_neutralize(s: pd.Series, group: pd.Series) -> pd.Series:
    """
    行业中性化：减去同行业均值
    group: pd.Series，index=ts_code，value=行业代码
    """
    result = s.copy()
    for g, idx in group.groupby(group).groups.items():
        common = s.index.intersection(idx)
        if len(common) > 0:
            result.loc[common] -= s.loc[common].mean()
    return result


def cs_scale(s: pd.Series) -> pd.Series:
    """截面缩放：除以绝对值之和，使截面总暴露为1"""
    abs_sum = s.abs().sum()
    return s / abs_sum if abs_sum > 0 else s


def cs_demean(s: pd.Series) -> pd.Series:
    """截面去均值"""
    return s - s.mean()


def cs_top_n(s: pd.Series, n: int) -> pd.Series:
    """返回 top-n 的 bool mask"""
    threshold = s.nlargest(n).min()
    return s >= threshold


def cs_bottom_n(s: pd.Series, n: int) -> pd.Series:
    """返回 bottom-n 的 bool mask"""
    threshold = s.nsmallest(n).max()
    return s <= threshold
