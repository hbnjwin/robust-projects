"""
services/gru_signal_generate.py — GRU 模型推理，生成每只股票的预测 score

输入: data/factors_latest.parquet（最新交易日因子）
输出: {ts_code: score} dict

用法:
    from services.gru_signal_generate import gru_predict
    scores = gru_predict()  # {ts_code: float}
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

_QUANT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_QUANT_ROOT))

GRU_MODEL_PATH = _QUANT_ROOT / "ml/model_store/v1/gru_model.pt"
FACTORS_PATH   = _QUANT_ROOT / "data/factors_latest.parquet"

_SKIP_COLS = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d",
              "corr_ret_vol_10", "corr_ret_vol_20"}


class _GRUModel(torch.nn.Module):
    def __init__(self, n_features, hidden_size=64, num_layers=2, dropout=0.1):
        super().__init__()
        self.gru = torch.nn.GRU(
            input_size=n_features, hidden_size=hidden_size,
            num_layers=num_layers, batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = torch.nn.Sequential(
            torch.nn.Linear(hidden_size, 32),
            torch.nn.ReLU(),
            torch.nn.Dropout(dropout),
            torch.nn.Linear(32, 1),
        )

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


def gru_predict(
    factors_path: str | None = None,
    model_path: str | None = None,
    batch_size: int = 1024,
    date_str: str | None = None,
) -> dict[str, float]:
    """
    用 GRU 模型对指定交易日（或最新日）所有股票打分。

    Args:
        date_str: 指定日期 "YYYY-MM-DD"，None 则取数据最新日期
    Returns:
        {ts_code: predicted_return_score}
    """
    fpath = Path(factors_path) if factors_path else FACTORS_PATH
    mpath = Path(model_path) if model_path else GRU_MODEL_PATH

    if not mpath.exists():
        print(f"[GRU] 模型文件不存在: {mpath}")
        return {}

    # ── 加载模型 ──────────────────────────────────────────────
    ckpt = torch.load(str(mpath), map_location="cpu")
    n_features   = ckpt["n_features"]
    hidden_size  = ckpt["hidden_size"]
    num_layers   = ckpt["num_layers"]
    dropout      = ckpt["dropout"]
    seq_len      = ckpt["seq_len"]
    feature_names = ckpt["feature_names"]

    model = _GRUModel(n_features, hidden_size, num_layers, dropout)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    print(f"[GRU] 模型加载: valid_IC={ckpt.get('valid_ic', 'N/A'):.4f}  "
          f"test_IC={ckpt.get('test_ic', 'N/A'):.4f}  seq_len={seq_len}")

    # ── 加载因子数据 ──────────────────────────────────────────
    df = pd.read_parquet(str(fpath))
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    latest_date = pd.Timestamp(date_str) if date_str else df["trade_date"].max()
    print(f"[GRU] 推理日期: {latest_date.date()}，股票数: {df['ts_code'].nunique()}")

    # 按股票构建时序窗口（取最近 seq_len 天）
    df = df.sort_values(["ts_code", "trade_date"])
    feat_cols = [c for c in feature_names if c in df.columns]

    scores: dict[str, float] = {}
    skipped = 0

    for ts_code, grp in df.groupby("ts_code"):
        grp = grp.sort_values("trade_date")
        # 只要最新日期在数据里
        if grp["trade_date"].max() < latest_date:
            skipped += 1
            continue

        feat = grp[feat_cols].values.astype(np.float32)
        if len(feat) < seq_len:
            skipped += 1
            continue

        # 取最后 seq_len 行作为输入窗口
        window = feat[-seq_len:]
        window = np.clip(np.nan_to_num(window, nan=0.0, posinf=3.0, neginf=-3.0), -3, 3)
        scores[ts_code] = window  # 暂存 array

    if not scores:
        print("[GRU] 无有效样本")
        return {}

    # ── 批量推理 ──────────────────────────────────────────────
    ts_codes = list(scores.keys())
    X = np.stack([scores[c] for c in ts_codes], axis=0)  # (N, seq_len, n_feat)

    result: dict[str, float] = {}
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            batch = torch.from_numpy(X[i:i + batch_size])
            preds = model(batch).numpy()
            for j, pred in enumerate(preds):
                result[ts_codes[i + j]] = float(pred)

    print(f"[GRU] 推理完成: {len(result)} 只股票，跳过 {skipped} 只")
    return result


if __name__ == "__main__":
    scores = gru_predict()
    top10 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    print("Top 10:", top10)
