"""
ML 信号生成器
加载训练好的模型 + 因子数据 + Regime标签 → 生成每日交易信号

信号格式兼容 FactorStrategy: {date_str: {ts_code: score}}
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.models import BaseModel


# 因子数据中不参与预测的列
_META_COLS = {"ts_code", "trade_date"}
_LABEL_COLS = {"label_3d", "label_5d", "label_10d"}
_SKIP_COLS = _META_COLS | _LABEL_COLS


class MLSignalGenerator:
    """
    ML 信号生成器

    用法 (回测):
        gen = MLSignalGenerator(
            model_dir="ml/model_store/v1",
            factors_path="data/factors_full.parquet",
            regime_path="data/regime_labels.parquet",
        )
        all_signals = gen.get_all_signals()
        # all_signals = {date_str: {ts_code: score}}

    用法 (实盘单日):
        signal = gen.get_daily_signal("2025-03-13", regime="BULL")
    """

    def __init__(
        self,
        model_dir: str,
        factors_path: str,
        regime_path: str,
    ):
        self.model_dir = Path(model_dir)

        # 加载模型
        self.models: dict[str, BaseModel] = {}
        for name in ["global", "bull", "crisis", "neutral"]:
            pkl_path = self.model_dir / f"{name}.pkl"
            if pkl_path.exists():
                self.models[name.upper()] = BaseModel.load(str(pkl_path))

        if "GLOBAL" not in self.models:
            raise FileNotFoundError(f"global.pkl not found in {model_dir}")

        # 加载元信息
        meta_path = self.model_dir / "meta.json"
        if meta_path.exists():
            with open(meta_path) as f:
                self.meta = json.load(f)
            self.feature_names = self.meta.get("feature_names", [])
        else:
            self.feature_names = []

        # 加载因子数据
        print(f"[signal] Loading factors from {factors_path}...")
        self.factors_df = pd.read_parquet(factors_path)
        self.factors_df["trade_date"] = pd.to_datetime(self.factors_df["trade_date"])

        # 识别因子列
        if not self.feature_names:
            self.feature_names = [
                c for c in self.factors_df.columns if c not in _SKIP_COLS
            ]

        # 加载 Regime 标签
        regime_df = pd.read_parquet(regime_path)
        regime_df["trade_date"] = pd.to_datetime(regime_df["trade_date"])
        self.regime_map: dict[str, str] = dict(
            zip(regime_df["trade_date"].dt.strftime("%Y-%m-%d"), regime_df["regime"])
        )

        # 按日期分组索引（加速查询）
        self._date_groups = dict(list(self.factors_df.groupby("trade_date")))

        dates = sorted(self._date_groups.keys())
        print(f"[signal] {len(dates)} trading days, "
              f"{len(self.feature_names)} features, "
              f"{len(self.models)} models loaded")

    def _select_model(self, regime: str) -> BaseModel:
        """根据 Re选择模型，fallback 到 GLOBAL"""
        model = self.models.get(regime, self.models["GLOBAL"])
        return model

    def get_daily_signal(
        self,
        trade_date: str,
        regime: str | None = None,
    ) -> dict[str, float]:
        """
        单日信号生成

        Parameters
        ----------
        trade_date : "YYYY-MM-DD"
        regime : "BULL" / "CRISIS" / "NEUTRAL", None=自动查表

        Returns
        -------
        {ts_code: signal_score}
        """
        dt = pd.Timestamp(trade_date)
        group = self._date_groups.get(dt)
        if group is None or group.empty:
            return {}

        # 确定 Regime
        if regime is None:
            regime = self.regime_map.get(trade_date, "NEUTRAL")

        model = self._select_model(regime)

        # 提取特征矩阵
        X = group[self.feature_names].values.astype(np.float32)
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # 预测
        scores = model.predict(X)

        # 构建信号字典
        ts_codes = group["ts_code"].values
        return {code: float(score) for code, score in zip(ts_codes, scores)}

    def get_all_signals(self) -> dict[str, dict[str, float]]:
        """
        批量生成所有日期的信号（回测用）

        Returns
        -------
        {date_str: {ts_code: score}}
        """
        all_signals = {}
        dates = sorted(self._date_groups.keys())

        for i, dt in enumerate(dates):
            date_str = dt.strftime("%Y-%m-%d")
            regime = self.regime_map.get(date_str, "NEUTRAL")
            signals = self.get_daily_signal(date_str, regime=regime)
            if signals:
                all_signals[date_str] = signals

            if (i + 1) % 200 == 0:
                print(f"[signal] {i+1}/{len(dates)} days processed...")

        print(f"[signal] Done: {len(all_signals)} days with signals")
        return all_signals
