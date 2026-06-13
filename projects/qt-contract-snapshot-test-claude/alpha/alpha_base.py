"""
AlphaBase
统一 Alpha 抽象接口
Created: 2026-03-25
Phase: 1
"""

from abc import ABC, abstractmethod
from typing import Dict


class AlphaBase(ABC):
    """
    所有 Alpha 必须继承该抽象类
    """

    @abstractmethod
    def generate(self, date: str) -> Dict[str, float]:
        """
        输入日期，输出截面 alpha 分数

        Returns:
            {ts_code: score}
        """
        pass
