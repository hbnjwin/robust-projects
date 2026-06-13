"""
services/hist_signal_generate.py — HIST 模型推理，生成每只股票的预测 score

输入: data/factors_latest.parquet（最新交易日因子）
输出: {ts_code: score} dict

用法:
    from services.hist_signal_generate import hist_predict
    scores = hist_predict()  # {ts_code: float}
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

_QUANT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_QUANT_ROOT))

HIST_MODEL_PATH = _QUANT_ROOT / "ml/model_store/v1/hist_model.pt"
GRU_MODEL_PATH  = _QUANT_ROOT / "ml/model_store/v1/gru_model.pt"
FACTORS_PATH    = _QUANT_ROOT / "data/factors_latest.parquet"
S2C_PATH        = "/vol1/qlib_data/stock2concept/stock2concept.npy"
SIDX_PATH       = "/vol1/qlib_data/stock2concept/stock_index.npy"

SEQ_LEN   = 20
D_FEAT    = 75
HIDDEN    = 128
N_LAYERS  = 2
DROPOUT   = 0.1

_SKIP_COLS = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d",
              "corr_ret_vol_10", "corr_ret_vol_20"}


# ── 模型定义 ──────────────────────────────────────────────────────────
class HISTModel(nn.Module):
    def __init__(self, d_feat, hidden_size, num_layers, dropout, n_concepts):
        super().__init__()
        self.rnn = nn.GRU(d_feat, hidden_size, num_layers,
                          batch_first=True,
                          dropout=dropout if num_layers > 1 else 0)
        self.concept_fc  = nn.Linear(hidden_size, n_concepts)
        self.concept_emb = nn.Linear(n_concepts, hidden_size)
        self.fc_out = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, x, concept_matrix):
        out, _ = self.rnn(x)
        h = out[:, -1, :]
        attn = torch.softmax(self.concept_fc(h), dim=-1)
        attn = attn * (concept_matrix + 1e-6)
        attn = attn / (attn.sum(dim=-1, keepdim=True) + 1e-8)
        concept_repr = self.concept_emb(attn)
        combined = torch.cat([h, concept_repr], dim=-1)
        return self.fc_out(combined).squeeze(-1)


def _ts2qlib(ts_code: str) -> str:
    code, mkt = ts_code.split(".")
    return mkt + code


def hist_predict(
    factors_path: str | None = None,
    model_path: str | None = None,
    batch_size: int = 1024,
    trade_date: str | None = None,
) -> dict[str, float]:
    """
    用 HIST 模型对指定交易日所有股票打分。

    Parameters
    ----------
    factors_path : 因子数据路径，None 则用 factors_latest.parquet（实盘）
    model_path   : 模型路径
    batch_size   : 推理批大小
    trade_date   : 指定日期 "YYYY-MM-DD"，None 则取数据最新日期
                   回测时传入具体日期，从 factors_full.parquet 读取

    Returns
    -------
    {ts_code: predicted_return_score}
    """
    # 回测模式：按日期从 factors_full 读取
    if trade_date is not None and factors_path is None:
        factors_path = str(_QUANT_ROOT / "data/factors_full.parquet")

    fpath = Path(factors_path) if factors_path else FACTORS_PATH
    mpath = Path(model_path) if model_path else HIST_MODEL_PATH

    if not mpath.exists():
        print(f"[HIST] 模型文件不存在: {mpath}，fallback 到 GRU")
        from services.gru_signal_generate import gru_predict
        return gru_predict(factors_path=str(fpath))

    # ── 加载 stock2concept ────────────────────────────────────
    s2c_matrix  = np.load(S2C_PATH)
    stock_index = np.load(SIDX_PATH, allow_pickle=True).item()
    n_concepts  = s2c_matrix.shape[1]
    unknown_idx = s2c_matrix.shape[0] - 1
    s2c_t = torch.from_numpy(s2c_matrix).float()
    print(f"[HIST] stock2concept: {s2c_matrix.shape}, concepts={n_concepts}")

    # ── 加载模型 ──────────────────────────────────────────────
    state_dict = torch.load(str(mpath), map_location="cpu")
    model = HISTModel(D_FEAT, HIDDEN, N_LAYERS, DROPOUT, n_concepts)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"[HIST] 模型加载成功: {mpath}")

    # ── 加载因子数据 ──────────────────────────────────────────
    if trade_date is not None:
        target_dt = pd.Timestamp(trade_date)
        # 多读 SEQ_LEN * 3 天历史，保证有足够的时序窗口
        start_dt = target_dt - pd.Timedelta(days=SEQ_LEN * 3)
        df = pd.read_parquet(str(fpath), filters=[
            ("trade_date", ">=", start_dt.date()),
            ("trade_date", "<=", target_dt.date()),
        ])
    else:
        df = pd.read_parquet(str(fpath))

    df["trade_date"] = pd.to_datetime(df["trade_date"])
    target_date = pd.Timestamp(trade_date) if trade_date else df["trade_date"].max()
    print(f"[HIST] 推理日期: {target_date.date()}，股票数: {df['ts_code'].nunique()}")

    feat_cols = [c for c in df.columns if c not in _SKIP_COLS]
    # 补齐到 D_FEAT 维（不足则补 0 列）
    if len(feat_cols) < D_FEAT:
        print(f"[HIST] 特征数 {len(feat_cols)} < {D_FEAT}，补零列")
    df = df.sort_values(["ts_code", "trade_date"])

    windows, ts_codes, sidx_list = [], [], []
    skipped = 0

    for ts_code, grp in df.groupby("ts_code"):
        grp = grp.sort_values("trade_date")
        if grp["trade_date"].max() < target_date:
            skipped += 1
            continue
        feat = grp[feat_cols].values.astype(np.float32)
        if len(feat) < SEQ_LEN:
            skipped += 1
            continue

        window = feat[-SEQ_LEN:]
        # 补齐特征维度
        if window.shape[1] < D_FEAT:
            pad = np.zeros((SEQ_LEN, D_FEAT - window.shape[1]), dtype=np.float32)
            window = np.concatenate([window, pad], axis=1)
        elif window.shape[1] > D_FEAT:
            window = window[:, :D_FEAT]

        window = np.clip(np.nan_to_num(window, nan=0.0, posinf=3.0, neginf=-3.0), -3, 3)

        qlib_code = _ts2qlib(ts_code)
        sidx = stock_index.get(qlib_code, unknown_idx)

        windows.append(window)
        ts_codes.append(ts_code)
        sidx_list.append(sidx)

    if not windows:
        print("[HIST] 无有效样本")
        return {}

    X    = np.stack(windows, axis=0)          # (N, SEQ_LEN, D_FEAT)
    sidx = np.array(sidx_list, dtype=np.int32)

    # ── 批量推理 ──────────────────────────────────────────────
    result: dict[str, float] = {}
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            x_batch    = torch.from_numpy(X[i:i + batch_size])
            sidx_batch = torch.from_numpy(sidx[i:i + batch_size]).long()
            concept_mat = s2c_t[sidx_batch]
            preds = model(x_batch, concept_mat).numpy()
            for j, pred in enumerate(preds):
                result[ts_codes[i + j]] = float(pred)

    print(f"[HIST] 推理完成: {len(result)} 只股票，跳过 {skipped} 只")
    return result


if __name__ == "__main__":
    scores = hist_predict()
    top10 = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    print("Top 10:", top10)
