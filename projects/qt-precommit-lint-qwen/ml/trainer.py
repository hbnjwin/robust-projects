"""
Regime 感知训练器
按 BULL/CRISIS/NEUTRAL 分组训练独立模型，预测时根据当前 Regime 选择对应模型。

这是我们相比 VNPy 的差异化设计：
- VNPy: 全量数据训练一个模型
- 我们: 不同市场环境训练不同模型，因子有效性随 Regime 变化
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ml.dataset import FactorDataset
from ml.models import BaseModel
from ml.models.lgb_model import LGBModel
from ml.models.lasso_model import LassoModel


class RegimeAwareTrainer:
    """
    Regime 分组训练器

    用法:
        trainer = RegimeAwareTrainer(dataset, regime_labels)
        trainer.train_all()
        pred = trainer.predict(X, regime="BULL")
        trainer.save_all("ml/model_store/v1")
    """

    REGIMES = ["BULL", "CRISIS", "NEUTRAL"]

    def __init__(
        self,
        dataset: FactorDataset,
        regime_labels: pd.DataFrame,
        model_type: str = "lgb",
        model_kwargs: dict | None = None,
    ):
        """
        Parameters
        ----------
        dataset : FactorDataset
        regime_labels : DataFrame with columns [trade_date, regime]
            每个交易日的 Regime 标签 (由 RegimeDetectorV2 回标生成)
        model_type : "lgb" | "lasso"
        model_kwargs : 模型超参数
        """
        self.dataset = dataset
        self.model_type = model_type
        self.model_kwargs = model_kwargs or {}

        # 解析 regime_labels
        regime_labels = regime_labels.copy()
        regime_labels["trade_date"] = pd.to_datetime(regime_labels["trade_date"])
        self.regime_map: dict[str, set] = {}
        for regime in self.REGIMES:
            dates = set(regime_labels.loc[regime_labels["regime"] == regime, "trade_date"])
            self.regime_map[regime] = dates

        # 模型存储
        self.models: dict[str, BaseModel] = {}
        self.metrics: dict[str, dict] = {}

        # 全量模型 (fallback)
        self.global_model: BaseModel | None = None
        self.global_metrics: dict = {}

    def _create_model(self) -> BaseModel:
        if self.model_type == "lgb":
            return LGBModel(**self.model_kwargs)
        elif self.model_type == "lasso":
            return LassoModel(**self.model_kwargs)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def train_all(self, min_samples: int = 5000) -> dict[str, dict]:
        """
        训练所有 Regime 模型 + 全量 fallback 模型

        Parameters
        ----------
        min_samples : 最少训练样本数，低于此数的 Regime 跳过（用全量模型兜底）

        Returns
        -------
        dict : {regime: mes}
        """
        results = {}

        # 1. 全量模型 (fallback)
        print(f"\n{'=' * 50}")
        print(f"Training GLOBAL model (all data)")
        print(f"{'=' * 50}")
        self.global_model = self._create_model()
        self.global_metrics = self.global_model.fit(self.dataset)
        results["GLOBAL"] = self.global_metrics

        # 2. 各 Regime 模型
        for regime in self.REGIMES:
            dates = self.regime_map.get(regime, set())
            if not dates:
                print(f"\n[SKIP] {regime}: no dates found")
                continue

            regime_ds = self.dataset.filter_by_dates(dates)
            train_count = len(regime_ds.get_train_df())

            if train_count < min_samples:
                print(f"\n[SKIP] {regime}: only {train_count} train samples (min={min_samples})")
                continue

            print(f"\n{'=' * 50}")
            print(f"Training {regime} model ({train_count:,} train samples, {len(dates)} days)")
            print(f"{'=' * 50}")

            model = self._create_model()
            metrics = model.fit(regime_ds)
            self.models[regime] = model
            self.metrics[regime] = metrics
            results[regime] = metrics

        print(f"\n{'=' * 50}")
        print(f"Training complete: GLOBAL + {list(self.models.keys())}")
        print(f"{'=' * 50}")

        return results

    def predict(self, X: np.ndarray, regime: str) -> np.ndarray:
        """
        用对应 Regime 的模型预测，如果该 Regime 没有模型则用全量模型
        """
        model = self.models.get(regime, self.global_model)
        if model is None:
            raise ValueError("No model available. Call train_all() first.")
        return model.predict(X)

    def save_all(self, dir_path: str) -> None:
        """保存所有模型"""
        base = Path(dir_path)
        base.mkdir(parents=True, exist_ok=True)

        if self.global_model:
            self.global_model.save(str(base / "global.pkl"))

        for regime, model in self.models.items():
            model.save(str(base / f"{regime.lower()}.pkl"))

        # 保存元信息
        import json

        meta = {
            "model_type": self.model_type,
            "model_kwargs": self.model_kwargs,
            "regimes_trained": list(self.models.keys()),
            "metrics": {k: v for k, v in self.metrics.items()},
            "global_metrics": self.global_metrics,
            "feature_names": self.dataset.get_feature_names(),
        }
        with open(base / "meta.json", "w") as f:
            json.dump(meta, f, indent=2, default=str)
        print(f"[trainer] saved all models to {dir_path}/")

    @classmethod
    def load_models(cls, dir_path: str) -> dict[str, BaseModel]:
        """加载所有模型"""
        base = Path(dir_path)
        models = {}

        global_path = base / "global.pkl"
        if global_path.exists():
            models["GLOBAL"] = BaseModel.load(str(global_path))

        for regime in cls.REGIMES:
            path = base / f"{regime.lower()}.pkl"
            if path.exists():
                models[regime] = BaseModel.load(str(path))

        print(f"[trainer] loaded models: {list(models.keys())}")
        return models

    def evaluate_test(self) -> dict[str, dict]:
        """在测试集上评估所有模型"""
        X_test, y_test = self.dataset.get_test()
        results = {}

        if self.global_model:
            pred = self.global_model.predict(X_test)
            mse = float(np.mean((pred - y_test) ** 2))
            ic = float(np.corrcoef(pred, y_test)[0, 1]) if len(y_test) > 1 else 0.0
            results["GLOBAL"] = {"test_mse": mse, "test_ic": ic}
            print(f"[GLOBAL] test_mse={mse:.6f}, test_ic={ic:.4f}")

        for regime, model in self.models.items():
            pred = model.predict(X_test)
            mse = float(np.mean((pred - y_test) ** 2))
            ic = float(np.corrcoef(pred, y_test)[0, 1]) if len(y_test) > 1 else 0.0
            results[regime] = {"test_mse": mse, "test_ic": ic}
            print(f"[{regime}] test_mse={mse:.6f}, test_ic={ic:.4f}")

        return results


def generate_regime_labels(
    start_date: str = "2016-01-01",
    end_date: str = "2025-12-31",
) -> pd.DataFrame:
    """
    用 RegimeDetectorV2 在市场指数代理上回标 Regime

    由于 daily_price 表中没有沪深300指数数据，
    使用全市场等权平均收盘价作为市场指数代理。

    Returns
    -------
    DataFrame[trade_date, regime]
    """
    import duckdb
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from config import PG_CONFIG
    from live.regime_detector_v2 import RegimeDetectorV2

    # 用 DuckDB 从 PG 计算每日全市场均价和总成交量
    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres;")
    host = PG_CONFIG["host"]
    if host == "localhost":
        host = "127.0.0.1"
    pg_str = (
        f"dbname={PG_CONFIG['dbname']} "
        f"user={PG_CONFIG['user']} "
        f"password={PG_CONFIG['password']} "
        f"host={host} "
        f"port={PG_CONFIG.get('port', 5432)}"
    )
    con.execute(f"ATTACH '{pg_str}' AS pg (TYPE POSTGRES, READ_ONLY)")

    market_df = con.execute(f"""
        SELECT
            trade_date,
            AVG(close) AS avg_close,
            SUM(vol) AS total_volume
        FROM pg.public.daily_price
        WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
          AND close > 0
        GROUP BY trade_date
        ORDER BY trade_date
    """).fetchdf()
    con.close()

    print(f"[regime] market proxy: {len(market_df)} trading days")

    # 用 RegimeDetectorV2 回标
    detector = RegimeDetectorV2()
    records = []
    for _, row in market_df.iterrows():
        detector.update(float(row["avg_close"]), float(row["total_volume"]))
        regime = detector.detect()
        records.append({"trade_date": row["trade_date"], "regime": regime})

    df = pd.DataFrame(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"])

    # 统计
    counts = df["regime"].value_counts()
    print(f"[regime] labels generated: {len(df)} days")
    for r in ["BULL", "CRISIS", "NEUTRAL"]:
        print(f"  {r}: {counts.get(r, 0)} days ({counts.get(r, 0) / len(df) * 100:.1f}%)")

    return df
