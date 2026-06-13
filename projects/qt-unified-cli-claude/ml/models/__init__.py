"""
模型基类
"""
from abc import ABC, abstractmethod
import pickle
from pathlib import Path

import numpy as np

from ml.dataset import FactorDataset


class BaseModel(ABC):
    """ML 模型抽象基类"""

    @abstractmethod
    def fit(self, dataset: FactorDataset) -> dict:
        """
        训练模型
        返回训练指标 dict (如 best_iteration, train_loss, valid_loss)
        """
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测"""
        ...

    def feature_importance(self) -> dict[str, float]:
        """返回特征重要性 {feature_name: importance}"""
        return {}

    def save(self, path: str) -> None:
        """持久化模型"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        print(f"[model] saved to {path}")

    @classmethod
    def load(cls, path: str) -> "BaseModel":
        """加载模型"""
        with open(path, "rb") as f:
            model = pickle.load(f)
        print(f"[model] loaded from {path}")
        return model
