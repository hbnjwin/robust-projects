"""
HISTAlpha Adapter
Phase 4 - HIST 接入 AlphaManager
支持实盘（最新日期）和回测（按日期推理）两种模式
Created: 2026-03-25
"""

from typing import Dict

from alpha.alpha_base import AlphaBase


class HISTAlpha(AlphaBase):
    """
    HIST 模型 Alpha Adapter

    实盘模式（默认）：
        alpha = HISTAlpha()
        scores = alpha.generate(date)  # 读 factors_latest.parquet

    回测模式：
        alpha = HISTAlpha(backtest_mode=True)
        scores = alpha.generate("2023-01-05")  # 从 factors_full.parquet 按日期推理
    """

    def __init__(self, backtest_mode: bool = False):
        self.backtest_mode = backtest_mode
        self._cache: Dict[str, Dict[str, float]] = {}

    def generate(self, date: str) -> Dict[str, float]:
        if date in self._cache:
            return self._cache[date]

        from services.hist_signal_generate import hist_predict

        if self.backtest_mode:
            scores = hist_predict(trade_date=date)
        else:
            scores = hist_predict()

        self._cache[date] = scores
        return scores
