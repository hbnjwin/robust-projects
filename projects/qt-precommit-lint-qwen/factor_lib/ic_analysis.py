"""
factor_lib/ic_analysis.py — 因子 IC 分析工具

IC (Information Coefficient): 因子值与未来收益的 Spearman 相关系数
ICIR = IC均值 / IC标准差（越高越稳定）

用法:
    from factor_lib.ic_analysis import ICAnalyzer
    analyzer = ICAnalyzer(factor_df, return_df)
    report = analyzer.run()
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


class ICAnalyzer:
    """
    因子 IC 分析器

    Parameters
    ----------
    factor_df : pd.DataFrame
        index=trade_date, columns=ts_code, values=factor_value
    return_df : pd.DataFrame
        index=trade_date, columns=ts_code, values=forward_return
        （通常是 N 日后收益，与 factor_df 对齐）
    """

    def __init__(self, factor_df: pd.DataFrame, return_df: pd.DataFrame):
        self.factor_df = factor_df
        self.return_df = return_df

    def daily_ic(self) -> pd.Series:
        """计算每日截面 IC（Spearman）"""
        dates = self.factor_df.index.intersection(self.return_df.index)
        ics = {}
        for date in dates:
            f = self.factor_df.loc[date].dropna()
            r = self.return_df.loc[date].dropna()
            common = f.index.intersection(r.index)
            if len(common) < 5:
                continue
            ic, _ = stats.spearmanr(f.loc[common], r.loc[common])
            ics[date] = ic
        return pd.Series(ics, name="IC")

    def daily_rank_ic(self) -> pd.Series:
        """Rank IC（等价于 Spearman，显式用排名计算）"""
        return self.daily_ic()

    def summary(self) -> dict:
        """IC 汇总统计"""
        ic_series = self.daily_ic()
        if ic_series.empty:
            return {}
        return {
            "IC_mean": round(float(ic_series.mean()), 4),
            "IC_std": round(float(ic_series.std()), 4),
            "ICIR": round(float(ic_series.mean() / ic_series.std()), 4) if ic_series.std() > 0 else 0.0,
            "IC_positive_rate": round(float((ic_series > 0).mean()), 4),
            "IC_abs_mean": round(float(ic_series.abs().mean()), 4),
            "n_days": len(ic_series),
        }

    def run(self, verbose: bool = True) -> dict:
        """运行完整分析，返回 summary dict"""
        result = self.summary()
        if verbose and result:
            print(f"IC均值:    {result['IC_mean']:+.4f}")
            print(f"IC标准差:  {result['IC_std']:.4f}")
            print(f"ICIR:      {result['ICIR']:+.4f}")
            print(f"IC>0占比:  {result['IC_positive_rate']:.1%}")
            print(f"IC绝对均值:{result['IC_abs_mean']:.4f}")
            print(f"有效天数:  {result['n_days']}")
        return result


def compute_factor_ic(
    factor_series: pd.Series,
    price_df: pd.DataFrame,
    forward_days: int = 5,
) -> dict:
    """
    便捷函数：从单因子 Series 和价格 DataFrame 直接计算 IC

    Parameters
    ----------
    factor_series : pd.Series
        MultiIndex (trade_date, ts_code) 或 DataFrame 格式
    price_df : pd.DataFrame
        index=trade_date, columns=ts_code, values=close_price
    forward_days : int
        预测未来 N 日收益

    Returns
    -------
    dict: IC 汇总统计
    """
    # 计算未来 N 日收益
    forward_return = price_df.pct_change(forward_days).shift(-forward_days)

    # 如果 factor_series 是 MultiIndex，转为 DataFrame
    if isinstance(factor_series.index, pd.MultiIndex):
        factor_df = factor_series.unstack(level="ts_code")
    else:
        factor_df = factor_series.to_frame().T

    analyzer = ICAnalyzer(factor_df, forward_return)
    return analyzer.run()


def factor_quantile_return(
    factor_df: pd.DataFrame,
    return_df: pd.DataFrame,
    n_quantiles: int = 5,
) -> pd.DataFrame:
    """
    因子分组收益分析（分位数组合）

    Returns
    -------
    pd.DataFrame: index=trade_date, columns=Q1..Q5, values=平均收益
    """
    dates = factor_df.index.intersection(return_df.index)
    records = []

    for date in dates:
        f = factor_df.loc[date].dropna()
        r = return_df.loc[date].dropna()
        common = f.index.intersection(r.index)
        if len(common) < n_quantiles * 2:
            continue

        f_common = f.loc[common]
        r_common = r.loc[common]

        try:
            labels = pd.qcut(f_common, n_quantiles, labels=False, duplicates="drop")
        except ValueError:
            continue

        row = {"date": date}
        for q in range(n_quantiles):
            mask = labels == q
            if mask.sum() > 0:
                row[f"Q{q + 1}"] = float(r_common[mask].mean())
        records.append(row)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records).set_index("date")
    return df
