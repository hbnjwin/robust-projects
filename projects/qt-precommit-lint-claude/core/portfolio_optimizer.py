"""
core/portfolio_optimizer.py — 组合权重优化器

移植自 qlib/contrib/strategy/optimizer/optimizer.py
不依赖 qlib 安装，纯 numpy/scipy 实现

支持四种优化方法:
  - inv  : 反波动率加权（默认，最简单稳健）
  - gmv  : 全局最小方差组合
  - rp   : 风险平价（等风险贡献）
  - mvo  : 均值方差优化（需要预期收益）

用法:
    from core.portfolio_optimizer import PortfolioOptimizer

    opt = PortfolioOptimizer(method="rp")
    weights = opt(cov_matrix, signals)   # 返回各股权重 Series
"""
from __future__ import annotations

import warnings
from typing import Optional, Union

import numpy as np
import pandas as pd
import scipy.optimize as so


class PortfolioOptimizer:
    """
    组合权重优化器

    参数:
        method      : 优化方法 inv/gmv/rp/mvo
        lamb        : 风险厌恶系数（mvo用，越大越重视收益）
        delta       : 换手率限制（0=不限制）
        alpha       : L2 正则化系数
        scale_return: 是否对预期收益做波动率归一化
        tol         : 优化收敛精度
    """

    OPT_GMV = "gmv"
    OPT_MVO = "mvo"
    OPT_RP  = "rp"
    OPT_INV = "inv"

    def __init__(
        self,
        method:       str   = "inv",
        lamb:         float = 0.0,
        delta:        float = 0.0,
        alpha:        float = 0.0,
        scale_return: bool  = True,
        tol:          float = 1e-8,
    ):
        assert method in [self.OPT_GMV, self.OPT_MVO, self.OPT_RP, self.OPT_INV]
        self.method       = method
        self.lamb         = lamb
        self.delta        = delta
        self.alpha        = alpha
        self.scale_return = scale_return
        self.tol          = tol

    def __call__(
        self,
        S:  Union[np.ndarray, pd.DataFrame],
        r:  Optional[Union[np.ndarray, pd.Series]] = None,
        w0: Optional[Union[np.ndarray, pd.Series]] = None,
    ) -> Union[np.ndarray, pd.Series]:
        """
        计算最优权重

        参数:
            S  : 协方差矩阵 (n×n)
            r  : 预期收益向量 (n,)，mvo 必须传，其他可选
            w0 : 当前持仓权重 (n,)，用于换手率控制

        返回:
            权重向量，和为1，非负（纯多头）
        """
        index = None
        if isinstance(S, pd.DataFrame):
            index = S.index
            S = S.values

        if r is not None:
            if isinstance(r, pd.Series):
                r = r.values
            r = np.array(r, dtype=float)

        if w0 is not None:
            if isinstance(w0, pd.Series):
                w0 = w0.values
            w0 = np.array(w0, dtype=float)

        # 预期收益归一化
        if r is not None and self.scale_return:
            std = r.std()
            if std > 0:
                r = r / std * np.sqrt(np.mean(np.diag(S)))

        w = self._optimize(S, r, w0)

        if index is not None:
            w = pd.Series(w, index=index)

        return w

    def _optimize(self, S, r, w0) -> np.ndarray:
        n = len(S)

        # ── 反波动率（最简单，不需要优化求解）────────────────
        if self.method == self.OPT_INV:
            vols = np.sqrt(np.diag(S))
            vols = np.where(vols > 0, vols, 1e-8)
            w = 1.0 / vols
            return w / w.sum()

        # ── 全局最小方差 ──────────────────────────────────────
        if self.method == self.OPT_GMV:
            def objective(w):
                return w @ S @ w + self.alpha * np.sum(w ** 2)

            return self._solve(n, objective, S, r=None, w0=w0)

        # ── 风险平价 ──────────────────────────────────────────
        if self.method == self.OPT_RP:
            def objective(w):
                port_var = w @ S @ w
                # 各股风险贡献
                rc = w * (S @ w) / (port_var + 1e-10)
                # 最小化风险贡献差异（等风险贡献）
                target = np.ones(n) / n
                return np.sum((rc - target) ** 2) + self.alpha * np.sum(w ** 2)

            return self._solve(n, objective, S, r=None, w0=w0)

        # ── 均值方差优化 ──────────────────────────────────────
        if self.method == self.OPT_MVO:
            if r is None:
                raise ValueError("mvo 方法需要传入预期收益 r")

            def objective(w):
                ret  = w @ r
                risk = w @ S @ w
                turn = 0.0
                if w0 is not None and self.delta > 0:
                    turn = self.delta * np.sum(np.abs(w - w0))
                return -self.lamb * ret + risk + turn + self.alpha * np.sum(w ** 2)

            return self._solve(n, objective, S, r=r, w0=w0)

        raise ValueError(f"未知优化方法: {self.method}")

    def _solve(self, n, objective, S, r, w0) -> np.ndarray:
        """通用约束优化求解"""
        # 初始权重
        x0 = np.ones(n) / n if w0 is None else w0.copy()
        x0 = np.clip(x0, 0, 1)
        x0 /= x0.sum() + 1e-10

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # 换手率约束
        if w0 is not None and self.delta > 0:
            constraints.append({
                "type": "ineq",
                "fun": lambda w: self.delta - np.sum(np.abs(w - w0))
            })

        bounds = [(0.0, 1.0)] * n

        result = so.minimize(
            objective, x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            tol=self.tol,
            options={"maxiter": 1000, "ftol": self.tol},
        )

        if not result.success:
            warnings.warn(f"优化未收敛: {result.message}，使用等权")
            return np.ones(n) / n

        w = np.clip(result.x, 0, 1)
        w /= w.sum() + 1e-10
        return w


# ── 便捷函数：从信号和历史收益计算协方差矩阵 ─────────────────

def compute_cov_from_returns(
    returns_df: pd.DataFrame,
    lookback:   int = 60,
    shrinkage:  float = 0.1,
) -> pd.DataFrame:
    """
    从历史收益率计算协方差矩阵（含 Ledoit-Wolf 收缩）

    参数:
        returns_df : DataFrame，index=日期，columns=ts_code，值=日收益率
        lookback   : 使用最近 N 天数据
        shrinkage  : 收缩系数（0=不收缩，1=对角矩阵）

    返回:
        协方差矩阵 DataFrame
    """
    recent = returns_df.tail(lookback).dropna(axis=1, how="any")
    S = recent.cov().values

    # Ledoit-Wolf 收缩：S = (1-α)S + α·diag(S)
    if shrinkage > 0:
        diag_S = np.diag(np.diag(S))
        S = (1 - shrinkage) * S + shrinkage * diag_S

    return pd.DataFrame(S, index=recent.columns, columns=recent.columns)


def optimize_weights(
    signals:    pd.Series,
    returns_df: pd.DataFrame,
    method:     str   = "rp",
    top_n:      int   = 20,
    lookback:   int   = 60,
    max_weight: float = 0.15,
) -> pd.Series:
    """
    一键优化：从 ML 信号 + 历史收益计算最优权重

    参数:
        signals    : ML 评分 Series（index=ts_code）
        returns_df : 历史日收益率 DataFrame
        method     : 优化方法
        top_n      : 先按信号选 top_n 只，再优化权重
        lookback   : 协方差计算窗口
        max_weight : 单股最大权重

    返回:
        权重 Series（index=ts_code，和为1）
    """
    # 按信号选 top_n
    top_codes = signals.nlargest(top_n).index.tolist()
    available = [c for c in top_codes if c in returns_df.columns]
    if not available:
        return pd.Series(dtype=float)

    # 计算协方差
    S = compute_cov_from_returns(returns_df[available], lookback=lookback)

    # 预期收益（用信号作为代理）
    r = signals.reindex(S.index).fillna(0)

    # 优化
    opt = PortfolioOptimizer(method=method, lamb=1.0)
    w = opt(S, r=r)

    # 单股上限
    w = w.clip(0, max_weight)
    w = w / w.sum()

    return w
