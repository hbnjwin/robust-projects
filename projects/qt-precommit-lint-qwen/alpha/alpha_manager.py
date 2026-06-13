"""
AlphaManager
负责 Alpha 注册、融合与标准化
Created: 2026-03-25
Phase: 4 - 加入标准化模块

标准化模式：
    None     → 不标准化（默认，保持等价性）
    "rank"   → 截面排名标准化 [0, 1]
    "zscore" → 截面 Z-score 标准化
"""

from typing import Dict, List, Optional

import numpy as np

from .alpha_base import AlphaBase


class AlphaManager:
    def __init__(self, standardize: Optional[str] = None):
        """
        Parameters
        ----------
        standardize : None | "rank" | "zscore"
            None     → 不标准化（默认）
            "rank"   → 截面排名归一化到 [0, 1]
            "zscore" → 截面 Z-score
        """
        self.alphas: List[AlphaBase] = []
        self.weights: List[float] = []
        self.standardize = standardize

    def register(self, alpha: AlphaBase, weight: float = 1.0):
        self.alphas.append(alpha)
        self.weights.append(weight)

    def generate(self, date: str) -> Dict[str, float]:
        if not self.alphas:
            return {}

        # 单 Alpha 且无标准化 → 直接透传（保持 Phase 3 等价性）
        if len(self.alphas) == 1 and self.standardize is None:
            return self.alphas[0].generate(date)

        # 多 Alpha 加权融合
        combined: Dict[str, float] = {}
        total_weight = sum(self.weights)
        for alpha, weight in zip(self.alphas, self.weights):
            scores = alpha.generate(date)
            w = weight / total_weight  # 归一化权重
            for code, value in scores.items():
                combined[code] = combined.get(code, 0.0) + w * value

        if self.standardize is None:
            return combined
        elif self.standardize == "rank":
            return self._rank_standardize(combined)
        elif self.standardize == "zscore":
            return self._zscore_standardize(combined)
        else:
            raise ValueError(f"Unknown standardize mode: {self.standardize}")

    def _rank_standardize(self, scores: Dict[str, float]) -> Dict[str, float]:
        """截面排名归一化到 [0, 1]，分数越高排名越高"""
        if not scores:
            return {}
        items = sorted(scores.items(), key=lambda x: x[1])
        n = len(items)
        return {code: i / (n - 1) if n > 1 else 0.5 for i, (code, _) in enumerate(items)}

    def _zscore_standardize(self, scores: Dict[str, float]) -> Dict[str, float]:
        """截面 Z-score 标准化"""
        if not scores:
            return {}
        values = np.array(list(scores.values()), dtype=float)
        mean = values.mean()
        std = values.std()
        if std == 0:
            return {k: 0.0 for k in scores}
        return {k: float((v - mean) / std) for k, v in scores.items()}
