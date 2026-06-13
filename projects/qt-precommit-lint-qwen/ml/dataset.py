"""
因子数据集管理
从 Parquet 加载因子数据，支持 train/valid/test 时间切分
"""

import numpy as np
import pandas as pd


# 不参与训练的列
_META_COLS = {"ts_code", "trade_date"}
_LABEL_COLS = {"label_3d", "label_5d", "label_10d"}


class FactorDataset:
    """
    因子数据集

    用法:
        ds = FactorDataset("data/factors.parquet",
                           train_period=("2016-01-01", "2022-12-31"),
                           valid_period=("2023-01-01", "2023-12-31"),
                           test_period=("2024-01-01", "2024-12-31"),
                           label_col="label_3d")
        X_train, y_train = ds.get_train()
    """

    def __init__(
        self,
        parquet_path: str,
        train_period: tuple[str, str],
        valid_period: tuple[str, str],
        test_period: tuple[str, str],
        label_col: str = "label_3d",
    ):
        self.label_col = label_col

        # 加载数据
        df = pd.read_parquet(parquet_path)

        # 确保 trade_date 是 datetime
        df["trade_date"] = pd.to_datetime(df["trade_date"])

        # 识别因子列
        self.feature_cols = [c for c in df.columns if c not in _META_COLS and c not in _LABEL_COLS]

        # 按时间切分
        self._train = self._slice(df, train_period)
        self._valid = self._slice(df, valid_period)
        self._test = self._slice(df, test_period)

        print(
            f"[FactorDataset] features={len(self.feature_cols)}, "
            f"train={len(self._train):,}, valid={len(self._valid):,}, "
            f"test={len(self._test):,}, label={label_col}"
        )

    def _slice(self, df: pd.DataFrame, period: tuple[str, str]) -> pd.DataFrame:
        start, end = pd.Timestamp(period[0]), pd.Timestamp(period[1])
        mask = (df["trade_date"] >= start) & (df["trade_date"] <= end)
        subset = df.loc[mask].copy()
        # 去掉 label 为 NaN 的行
        subset = subset.dropna(subset=[self.label_col])
        return subset

    def _to_xy(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        X = df[self.feature_cols].values.astype(np.float32)
        y = df[self.label_col].values.astype(np.float32)
        # 将 NaN/Inf 替换为 0
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        y = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0)
        return X, y

    def get_train(self) -> tuple[np.ndarray, np.ndarray]:
        return self._to_xy(self._train)

    def get_valid(self) -> tuple[np.ndarray, np.ndarray]:
        return self._to_xy(self._valid)

    def get_test(self) -> tuple[np.ndarray, np.ndarray]:
        return self._to_xy(self._test)

    def get_feature_names(self) -> list[str]:
        return list(self.feature_cols)

    def get_train_df(self) -> pd.DataFrame:
        """返回训练集 DataFrame（含 ts_code, trade_date，用于 Regime 过滤）"""
        return self._train

    def get_valid_df(self) -> pd.DataFrame:
        return self._valid

    def get_test_df(self) -> pd.DataFrame:
        return self._test

    def filter_by_dates(self, dates: set) -> "FactorDataset":
        """
        返回一个新的 FactorDataset，只保留指定日期的数据。
        用于 Regime 分组训练。
        """
        new = object.__new__(FactorDataset)
        new.label_col = self.label_col
        new.feature_cols = self.feature_cols
        new._train = self._train[self._train["trade_date"].isin(dates)]
        new._valid = self._valid[self._valid["trade_date"].isin(dates)]
        new._test = self._test[self._test["trade_date"].isin(dates)]
        return new
