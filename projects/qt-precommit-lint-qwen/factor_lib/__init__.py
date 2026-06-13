"""
factor_lib — 因子函数库

模块:
  ts_factors  时序因子（单股票时序操作）
  cs_factors  截面因子（跨股票截面操作）
  ic_analysis IC 分析工具
"""

from factor_lib.ts_factors import (
    ts_delay,
    ts_delta,
    ts_pct,
    ts_mean,
    ts_std,
    ts_min,
    ts_max,
    ts_sum,
    ts_rank,
    ts_argmax,
    ts_argmin,
    ts_corr,
    ts_cov,
    ts_slope,
    ts_rsquare,
    ts_resi,
    ts_quantile,
    ts_zscore,
    factor_rsi,
    factor_macd_diff,
    factor_macd_hist,
    factor_boll_pos,
    factor_atr,
    alpha_001,
    alpha_006,
    alpha_013,
    alpha_016,
    alpha_028,
)
from factor_lib.cs_factors import (
    cs_rank,
    cs_zscore,
    cs_robust_zscore,
    cs_winsorize,
    cs_neutralize,
    cs_scale,
    cs_demean,
    cs_top_n,
    cs_bottom_n,
)
from factor_lib.ic_analysis import (
    ICAnalyzer,
    compute_factor_ic,
    factor_quantile_return,
)

__all__ = [
    # ts
    "ts_delay",
    "ts_delta",
    "ts_pct",
    "ts_mean",
    "ts_std",
    "ts_min",
    "ts_max",
    "ts_sum",
    "ts_rank",
    "ts_argmax",
    "ts_argmin",
    "ts_corr",
    "ts_cov",
    "ts_slope",
    "ts_rsquare",
    "ts_resi",
    "ts_quantile",
    "ts_zscore",
    "factor_rsi",
    "factor_macd_diff",
    "factor_macd_hist",
    "factor_boll_pos",
    "factor_atr",
    "alpha_001",
    "alpha_006",
    "alpha_013",
    "alpha_016",
    "alpha_028",
    # cs
    "cs_rank",
    "cs_zscore",
    "cs_robust_zscore",
    "cs_winsorize",
    "cs_neutralize",
    "cs_scale",
    "cs_demean",
    "cs_top_n",
    "cs_bottom_n",
    # ic
    "ICAnalyzer",
    "compute_factor_ic",
    "factor_quantile_return",
]
