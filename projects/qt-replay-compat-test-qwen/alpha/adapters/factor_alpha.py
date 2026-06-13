"""
FactorAlpha Adapter
Phase 2
封装现有 factor_scores 字典
不改变现有逻辑
"""

from typing import Dict

from alpha.alpha_base import AlphaBase


class FactorAlpha(AlphaBase):
    def __init__(self, factor_scores: Dict[str, Dict[str, float]]):
        self.factor_scores = factor_scores

    def generate(self, date: str) -> Dict[str, float]:
        return self.factor_scores.get(date, {})
