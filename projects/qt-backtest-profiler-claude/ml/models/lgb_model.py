"""
LightGBM 模型
主力预测模型，适合表格数据，训练快，可解释性好
"""
import numpy as np
import lightgbm as lgb

from ml.dataset import FactorDataset
from ml.models import BaseModel


class LGBModel(BaseModel):
    """
    LightGBM 梯度提升树模型

    参数针对 A 股全市场因子数据优化:
    - 降低学习率 (数据量大)
    - feature_fraction / bagging 防过拟合
    - early stopping 自动选最优轮数
    """

    def __init__(
        self,
        learning_rate: float = 0.05,
        num_leaves: int = 63,
        num_boost_round: int = 2000,
        early_stopping_rounds: int = 100,
        feature_fraction: float = 0.8,
        bagging_fraction: float = 0.8,
        bagging_freq: int = 5,
        lambda_l1: float = 0.1,
        lambda_l2: float = 0.1,
        min_child_samples: int = 50,
        seed: int = 42,
        verbose: int = 50,
    ):
        self.params = {
            "objective": "mse",
            "metric": "mse",
            "learning_rate": learning_rate,
            "num_leaves": num_leaves,
            "feature_fraction": feature_fraction,
            "bagging_fraction": bagging_fraction,
            "bagging_freq": bagging_freq,
            "lambda_l1": lambda_l1,
            "lambda_l2": lambda_l2,
            "min_child_samples": min_child_samples,
            "seed": seed,
            "verbose": -1,
        }
        self.num_boost_round = num_boost_round
        self.early_stopping_rounds = early_stopping_rounds
        self.verbose = verbose

        self.model: lgb.Booster | None = None
        self.feature_names: list[str] = []
        self.best_iteration: int = 0

    def fit(self, dataset: FactorDataset) -> dict:
        X_train, y_train = dataset.get_train()
        X_valid, y_valid = dataset.get_valid()
        self.feature_names = dataset.get_feature_names()

        train_ds = lgb.Dataset(X_train, label=y_train, feature_name=self.feature_names)

        has_valid = len(X_valid) > 0
        callbacks = [lgb.log_evaluation(self.verbose)]
        if has_valid:
            valid_ds = lgb.Dataset(X_valid, label=y_valid, feature_name=self.feature_names, reference=train_ds)
            callbacks.append(lgb.early_stopping(self.early_stopping_rounds))
            valid_sets = [train_ds, valid_ds]
            valid_names = ["train", "valid"]
        else:
            print("  [WARN] 验证集为空，跳过 early stopping")
            valid_sets = [train_ds]
            valid_names = ["train"]

        self.model = lgb.train(
            self.params,
            train_ds,
            num_boost_round=self.num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        self.best_iteration = self.model.best_iteration

        # 评估指标
        train_pred = self.model.predict(X_train)
        train_mse = float(np.mean((train_pred - y_train) ** 2))
        if len(X_valid) > 0:
            valid_pred = self.model.predict(X_valid)
            valid_mse = float(np.mean((valid_pred - y_valid) ** 2))
        else:
            valid_mse = float('nan')

        metrics = {
            "best_iteration": self.best_iteration,
            "train_mse": train_mse,
            "valid_mse": valid_mse,
            "train_samples": len(y_train),
            "valid_samples": len(y_valid),
        }
        print(f"[LGB] best_iter={self.best_iteration}, "
              f"train_mse={train_mse:.6f}, valid_mse={valid_mse:.6f}")
        return metrics

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise ValueError("Model not fitted yet")
        return self.model.predict(X, num_iteration=self.best_iteration)

    def feature_importance(self) -> dict[str, float]:
        if self.model is None:
            return {}
        importance = self.model.feature_importance(importance_type="gain")
        total = importance.sum()
        if total == 0:
            return {}
        return {
            name: float(imp / total)
            for name, imp in zip(self.feature_names, importance)
        }

    def top_features(self, n: int = 20) -> list[tuple[str, float]]:
        """返回 top-n 重要因子"""
        fi = self.feature_importance()
        return sorted(fi.items(), key=lambda x: x[1], reverse=True)[:n]
