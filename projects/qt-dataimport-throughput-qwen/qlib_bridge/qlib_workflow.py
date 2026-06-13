"""
qlib_bridge/qlib_workflow.py — 用 qlib 原生框架跑回测

适配我们的预计算因子数据（不用 Alpha158/Alpha360）
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import qlib
from qlib.config import REG_CN
from qlib.data import D
from qlib.data.dataset import DatasetH, TSDatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.contrib.model.gbdt import LGBModel
from qlib.contrib.model.pytorch_gru_ts import GRU as QlibGRU
from qlib.contrib.strategy import TopkDropoutStrategy
from qlib.contrib.evaluate import risk_analysis, backtest_daily
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, SigAnaRecord, PortAnaRecord

import numpy as np
import pandas as pd

QLIB_DATA_DIR = "/vol1/qlib_data"

# 我们的因子列（与 factors_full.parquet 一致）
FEATURE_COLS = [
    "kmid", "klen", "kmid2", "kup", "kup2", "klow", "klow2", "ksft", "ksft2",
    "open_ratio", "high_ratio", "low_ratio", "vwap_ratio",
    "roc_5", "roc_10", "roc_20", "roc_30", "roc_60",
    "ma_5", "ma_10", "ma_20", "ma_30", "ma_60",
    "std_5", "std_10", "std_20", "std_30", "std_60",
    "beta_5", "beta_10", "beta_20", "beta_30", "beta_60",
    "rsqr_5", "rsqr_10", "rsqr_20", "rsqr_30", "rsqr_60",
    "max_20", "max_60", "min_20", "min_60",
    "rsv_5", "rsv_20", "rsv_60",
    "qtlu_20", "qtld_20", "qtlu_60", "qtld_60",
    "vma_5", "vma_20", "vstd_5", "vstd_20", "vstd_60", "vol_ratio",
    "cntp_5", "cntp_10", "cntp_20", "cntd_5", "cntd_10", "cntd_20",
    "sump_5", "sump_20", "sumn_5", "sumn_20", "sumd_5", "sumd_20",
    "wvma_5", "wvma_10", "wvma_20",
    "vsump_5", "vsump_20", "vsumd_20",
]

LABEL_COL = "label_5d"


def init_qlib():
    qlib.init(provider_uri=QLIB_DATA_DIR, region=REG_CN)
    print(f"[qlib] initialized, data_dir={QLIB_DATA_DIR}")


def build_dataset(
    train_start="2022-01-01", train_end="2024-06-30",
    valid_start="2024-07-01", valid_end="2025-06-30",
    test_start="2025-07-01",  test_end="2026-03-13",
):
    """构建 qlib DatasetH，使用我们的预计算因子"""
    feature_fields = [f"${col}" for col in FEATURE_COLS]
    label_field = [f"${LABEL_COL}"]

    handler_config = {
        "start_time": train_start,
        "end_time": test_end,
        "instruments": "all",
        "data_loader": {
            "class": "QlibDataLoader",
            "kwargs": {
                "config": {
                    "feature": (feature_fields, FEATURE_COLS),
                    "label": (label_field, [LABEL_COL]),
                },
            },
        },
        "infer_processors": [
            {"class": "RobustZScoreNorm", "kwargs": {
                "fields_group": "feature", "clip_outlier": True,
                "fit_start_time": train_start, "fit_end_time": train_end,
            }},
            {"class": "Fillna", "kwargs": {"fields_group": "feature"}},
        ],
        "learn_processors": [
            {"class": "DropnaLabel"},
            {"class": "CSRankNorm", "kwargs": {"fields_group": "label"}},
        ],
    }

    handler = init_instance_by_config(
        {"class": "DataHandlerLP", "module_path": "qlib.data.dataset.handler", "kwargs": handler_config}
    )

    dataset = DatasetH(
        handler=handler,
        segments={
            "train": (train_start, train_end),
            "valid": (valid_start, valid_end),
            "test":  (test_start,  test_end),
        },
    )
    return dataset


def run_lgb(dataset):
    """用 qlib 原生 LightGBM 训练+回测"""
    model = LGBModel(
        loss="mse",
        colsample_bytree=0.8879,
        learning_rate=0.0421,
        subsample=0.8789,
        lambda_l1=205.6999,
        lambda_l2=580.9768,
        max_depth=8,
        num_leaves=210,
        num_threads=4,
        early_stopping_rounds=50,
        num_boost_round=1000,
    )

    with R.start(experiment_name="lgb_quant"):
        model.fit(dataset)
        R.save_objects(**{"trained_model.pkl": model})

        rec = R.get_recorder()
        sr = SignalRecord(model, dataset, rec)
        sr.generate()

        sar = SigAnaRecord(rec, ana_long_short=False, ann_scaler=252)
        sar.generate()

        print("\n[qlib LGB] 信号分析完成")
        metrics = rec.list_metrics()
        print(f"  Metrics: {metrics}")

    return rec


def run_gru(dataset):
    """用 qlib 原生 GRU 训练+信号分析"""
    # qlib GRU 需要 TSDatasetH，重新构建
    from qlib.data.dataset import TSDatasetH

    ts_dataset = TSDatasetH(
        handler=dataset.handler,
        segments=dataset.segments,
        step_len=20,
    )

    model = QlibGRU(
        d_feat=len(FEATURE_COLS),
        hidden_size=64,
        num_layers=2,
        dropout=0.1,
        n_epochs=30,
        lr=1e-3,
        early_stop=5,
        batch_size=2048,
        metric="loss",
        loss="mse",
        n_jobs=4,
        GPU=-1,  # CPU mode
    )

    with R.start(experiment_name="gru_quant"):
        model.fit(ts_dataset)
        R.save_objects(**{"trained_model.pkl": model})

        rec = R.get_recorder()
        sr = SignalRecord(model, ts_dataset, rec)
        sr.generate()

        sar = SigAnaRecord(rec, ana_long_short=False, ann_scaler=252)
        sar.generate()

        print("\n[qlib GRU] 信号分析完成")
        metrics = rec.list_metrics()
        print(f"  Metrics: {metrics}")

    return rec


def main():
    init_qlib()
    print("\n── 构建数据集 ──")
    dataset = build_dataset()
    print("  数据集构建完成")

    print("\n── GRU 训练+信号分析 ──")
    gru_rec = run_gru(dataset)

    print("\n[qlib] 全部完成 ✅")


if __name__ == "__main__":
    main()
