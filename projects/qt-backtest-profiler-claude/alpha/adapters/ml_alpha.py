"""
MLAlpha Adapter
Phase 2
封装现有 MLSignalGenerator
不改变现有逻辑
"""

from typing import Dict

from alpha.alpha_base import AlphaBase
from signals.signal_generator import MLSignalGenerator


class MLAlpha(AlphaBase):
    def __init__(self, model_dir: str, factors_path: str, regime_path: str):
        self.generator = MLSignalGenerator(
            model_dir=model_dir,
            factors_path=factors_path,
            regime_path=regime_path,
        )

    def generate(self, date: str) -> Dict[str, float]:
        return self.generator.get_daily_signal(date)
