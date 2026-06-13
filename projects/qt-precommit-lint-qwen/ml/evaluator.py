"""
模型评估工具
IC/IR 分析、分层回测、特征重要性报告
"""

import numpy as np
import pandas as pd

from ml.dataset import FactorDataset
from ml.models import BaseModel


def calc_daily_ic(
    dataset: FactorDataset,
    model: BaseModel,
    segment: str = "test",
) -> pd.DataFrame:
    """
    计算每日截面 IC (Information Coefficient)

    IC = corr(预测值, 真实收益) 在每个交易日的截面上计算

    Returns
    -------
    DataFrame[trade_date, ic, count]
    """
    if segment == "test":
        df = dataset.get_test_df()
    elif segment == "valid":
        df = dataset.get_valid_df()
    else:
        df = dataset.get_train_df()

    X = df[dataset.feature_cols].values.astype(np.float32)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    pred = model.predict(X)
    df = df.copy()
    df["pred"] = pred

    records = []
    for date, group in df.groupby("trade_date"):
        y_true = group[dataset.label_col].values
        y_pred = group["pred"].values

        # 去掉 NaN
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true = y_true[mask]
        y_pred = y_pred[mask]

        if len(y_true) < 10:
            continue

        ic = np.corrcoef(y_pred, y_true)[0, 1]
        if np.isnan(ic):
            ic = 0.0

        records.append({"trade_date": date, "ic": ic, "count": len(y_true)})

    result = pd.DataFrame(records)
    return result


def ic_summary(ic_df: pd.DataFrame) -> dict:
    """
    IC 汇总统计

    Returns
    -------
    dict: ic_mean, ic_std, icir, ic_positive_ratio
    """
    if ic_df.empty:
        return {"ic_mean": 0, "ic_std": 0, "icir": 0, "ic_positive_ratio": 0}

    ic_mean = float(ic_df["ic"].mean())
    ic_std = float(ic_df["ic"].std())
    icir = ic_mean / ic_std if ic_std > 0 else 0.0
    ic_pos = float((ic_df["ic"] > 0).mean())

    return {
        "ic_mean": round(ic_mean, 4),
        "ic_std": round(ic_std, 4),
        "icir": round(icir, 4),
        "ic_positive_ratio": round(ic_pos, 4),
        "days": len(ic_df),
    }


def print_evaluation_report(
    dataset: FactorDataset,
    model: BaseModel,
    model_name: str = "Model",
):
    """打印完整评估报告"""
    print(f"\n{'=' * 60}")
    print(f"  Evaluation Report: {model_name}")
    print(f"{'=' * 60}")

    # 1. IC 分析
    for seg in ["valid", "test"]:
        ic_df = calc_daily_ic(dataset, model, segment=seg)
        summary = ic_summary(ic_df)
        print(f"\n  [{seg.upper()}] IC Analysis ({summary['days']} days):")
        print(f"    IC Mean:     {summary['ic_mean']:.4f}")
        print(f"    IC Std:      {summary['ic_std']:.4f}")
        print(f"    ICIR:        {summary['icir']:.4f}")
        print(f"    IC > 0:      {summary['ic_positive_ratio']:.1%}")

    # 2. 特征重要性 Top 20
    fi = model.feature_importance()
    if fi:
        top = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:20]
        print(f"\n  Top 20 Features:")
        for i, (name, imp) in enumerate(top, 1):
            print(f"    {i:2d}. {name:25s} {imp:.4f}")

    print(f"\n{'=' * 60}\n")
