"""
Lasso 回归模型
用于因子筛选（非零系数 = 有效因子）和作为基线模型对比
"""

import numpy as np
from sklearn.linear_model import Lasso

from ml.dataset import FactorDataset
from ml.models import BaseModel


class LassoModel(BaseModel):
    """
    Lasso 回归 (L1 正则化)

    主要用途:
    1. 因子筛选: 非零系数的因子 = 有预测力的因子
    2. 基线模型: 与 LightGBM 对比，衡量非线性增益
    """

    def __init__(
        self,
        alpha: float = 0.0005,
        max_iter: int = 2000,
        random_state: int = 42,
    ):
        self.alpha = alpha
        self.max_iter = max_iter
        self.random_state = random_state

        self.model: Lasso | None = None
        self.feature_names: list[str] = []

    def fit(self, dataset: FactorDataset) -> dict:
        X_train, y_train = dataset.get_train()
        X_valid, y_valid = dataset.get_valid()
        self.feature_names = dataset.get_feature_names()

        # Lasso 合并 train+valid 训练（无 early stopping）
        X = np.vstack([X_train, X_valid])
        y = np.concatenate([y_train, y_valid])

        self.model = Lasso(
            alpha=self.alpha,
            max_iter=self.max_iter,
            random_state=self.random_state,
            fit_intercept=False,
            copy_X=False,
        )
        self.model.fit(X, y)

        # 评估
        train_pred = self.model.predict(X_train)
        valid_pred = self.model.predict(X_valid)
        train_mse = float(np.mean((train_pred - y_train) ** 2))
        valid_mse = float(np.mean((valid_pred - y_valid) ** 2))

        nonzero = int(np.sum(self.model.coef_ != 0))
        total = len(self.model.coef_)

        metrics = {
            "train_mse": train_mse,
            "valid_mse": valid_mse,
            "nonzero_features": nonzero,
            "total_features": total,
            "train_samples": len(y_train),
            "valid_samples": len(y_valid),
        }
        print(f"[Lasso] nonzero={nonzero}/{total}, train_mse={train_mse:.6f}, valid_mse={valid_mse:.6f}")
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("Model not fitted yet")
        return self.model.predict(X)

    def feature_importance(self) -> dict[str, float]:
        if self.model is None:
            return {}
        coef = np.abs(self.model.coef_)
        total = coef.sum()
        if total == 0:
            return {}
        return {name: float(c / total) for name, c in zip(self.feature_names, coef)}

    def selected_features(self) -> list[tuple[str, float]]:
        """返回非零系数的因子（即 Lasso 选中的因子）"""
        if self.model is None:
            return []
        result = [(name, float(coef)) for name, coef in zip(self.feature_names, self.model.coef_) if coef != 0]
        result.sort(key=lambda x: abs(x[1]), reverse=True)
        return result
