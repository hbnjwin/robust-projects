"""
qlib_bridge/train_gru.py — 用 quant 因子数据训练 qlib GRU 模型

不依赖 qlib 的数据层（不需要 qlib init），直接用适配器转换后的 numpy 数据
训练 GRU 模型，与现有 LightGBM 模型做 IC 对比

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python qlib_bridge/train_gru.py
"""
from __future__ import annotations

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from scipy.stats import spearmanr

_QUANT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_QUANT_ROOT))

from qlib_bridge.adapter import QuantDataAdapter


# ── GRU 模型定义 ─────────────────────────────────────────────
class GRUModel(nn.Module):
    """
    简单 GRU 时序预测模型
    输入: (batch, seq_len, n_features)
    输出: (batch,) 预测收益率
    """

    def __init__(self, n_features: int, hidden_size: int = 64, num_layers: int = 2, dropout: float = 0.1):
        super().__init__()
        self.gru = nn.GRU(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


# ── IC 计算 ───────────────────────────────────────────────────
def compute_ic(y_pred: np.ndarray, y_true: np.ndarray) -> float:
    """Spearman IC"""
    mask = ~(np.isnan(y_pred) | np.isnan(y_true))
    if mask.sum() < 10:
        return 0.0
    ic, _ = spearmanr(y_pred[mask], y_true[mask])
    return float(ic)


# ── 训练主流程 ────────────────────────────────────────────────
def train(
    seq_len:     int   = 20,
    hidden_size: int   = 64,
    num_layers:  int   = 2,
    dropout:     float = 0.1,
    n_epochs:    int   = 30,
    lr:          float = 1e-3,
    batch_size:  int   = 512,
    early_stop:  int   = 5,
    label_col:   str   = "label_5d",
    save_path:   str   = "ml/model_store/v1/gru_model.pt",
    train_start: str   = "2022-01-01",
    train_end:   str   = "2024-06-30",
    valid_start: str   = "2024-07-01",
    valid_end:   str   = "2025-06-30",
    test_start:  str   = "2025-07-01",
    test_end:    str   = "2026-03-13",
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[GRU] 设备: {device}")

    # ── 加载数据 ─────────────────────────────────────────────
    adapter = QuantDataAdapter(label_col=label_col)
    segments = adapter.build_dataset(
        train_start=train_start, train_end=train_end,
        valid_start=valid_start, valid_end=valid_end,
        test_start=test_start,  test_end=test_end,
    )
    numpy_data = adapter.to_numpy(segments, seq_len=seq_len)
    feature_names = adapter.get_feature_names()
    n_features = len(feature_names)
    print(f"[GRU] 特征数: {n_features}")

    # ── 构建 DataLoader（memmap 友好，按 batch 读取，不全量加载）──
    class MmapDataset(torch.utils.data.Dataset):
        def __init__(self, X_mmap, y_mmap):
            self.X = X_mmap
            self.y = y_mmap
        def __len__(self):
            return len(self.y)
        def __getitem__(self, idx):
            x = self.X[idx].copy()  # copy 触发实际读盘，避免 memmap 引用累积
            x = np.clip(np.nan_to_num(x, nan=0.0, posinf=3.0, neginf=-3.0), -3, 3)
            return torch.from_numpy(x), torch.tensor(self.y[idx], dtype=torch.float32)

    def make_loader(split: str, shuffle: bool) -> DataLoader:
        X, y, _ = numpy_data[split]
        ds = MmapDataset(X, y)
        return DataLoader(ds, batch_size=batch_size, shuffle=shuffle,
                          num_workers=2, pin_memory=False)

    train_loader = make_loader("train", shuffle=True)
    valid_loader = make_loader("valid", shuffle=False)

    # ── 模型 ─────────────────────────────────────────────────
    model = GRUModel(n_features, hidden_size, num_layers, dropout).to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    criterion = nn.MSELoss()

    param_count = sum(p.numel() for p in model.parameters())
    print(f"[GRU] 参数量: {param_count:,}")

    # ── 训练循环 ─────────────────────────────────────────────
    best_ic = -999
    best_epoch = 0
    best_state = None

    for epoch in range(1, n_epochs + 1):
        t0 = time.time()

        # Train
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            pred = model(X_batch)
            loss = criterion(pred, y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item()
        train_loss /= len(train_loader)

        # Valid
        model.eval()
        preds, trues = [], []
        with torch.no_grad():
            for X_batch, y_batch in valid_loader:
                X_batch = X_batch.to(device)
                pred = model(X_batch).cpu().numpy()
                preds.append(pred)
                trues.append(y_batch.numpy())
        preds = np.concatenate(preds)
        trues = np.concatenate(trues)
        valid_ic = compute_ic(preds, trues)

        scheduler.step(-valid_ic)
        elapsed = time.time() - t0

        print(f"  Epoch {epoch:3d}/{n_epochs}  loss={train_loss:.6f}  valid_IC={valid_ic:.4f}  ({elapsed:.1f}s)")

        if valid_ic > best_ic:
            best_ic = valid_ic
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch - best_epoch >= early_stop:
            print(f"[GRU] Early stop at epoch {epoch}, best epoch={best_epoch}")
            break

    # ── 测试集评估 ────────────────────────────────────────────
    print(f"\n[GRU] 最佳 valid IC={best_ic:.4f} (epoch {best_epoch})")
    model.load_state_dict(best_state)
    model.eval()

    # ── test 集可能为空（如 retrain 时 test_end 早于最新数据）────
    test_ic = float("nan")
    if "test" not in numpy_data or numpy_data["test"] is None:
        print("[GRU] test 集为空，跳过测试评估")
    else:
        X_test, y_test, test_idx = numpy_data["test"]
        if len(y_test) == 0:
            print("[GRU] test 集样本数为 0，跳过测试评估")
        else:
            # 分批处理，避免大数组一次性加载进内存
            test_preds = []
            with torch.no_grad():
                for i in range(0, len(X_test), batch_size):
                    chunk = X_test[i:i+batch_size].copy()  # memmap copy，避免引用累积
                    chunk = np.clip(np.nan_to_num(chunk, nan=0.0, posinf=3.0, neginf=-3.0), -3, 3)
                    batch = torch.from_numpy(chunk).to(device)
                    test_preds.append(model(batch).cpu().numpy())
                    del chunk, batch  # 及时释放
            test_preds = np.concatenate(test_preds)
            test_ic = compute_ic(test_preds, y_test)
            print(f"[GRU] 测试集 IC={test_ic:.4f}")

    # ── 与 LGB 对比 ───────────────────────────────────────────
    print("\n[GRU] 与现有 LGB 模型 IC 对比:")
    print(f"  LGB (验证集 2023):  IC=0.0290  ICIR=0.3995")
    print(f"  GRU (验证集):       IC={best_ic:.4f}")
    print(f"  GRU (测试集):       IC={test_ic:.4f}")

    # ── 保存模型 ─────────────────────────────────────────────
    save_dir = _QUANT_ROOT / Path(save_path).parent
    save_dir.mkdir(parents=True, exist_ok=True)
    full_path = _QUANT_ROOT / save_path

    torch.save({
        "model_state": best_state,
        "n_features": n_features,
        "hidden_size": hidden_size,
        "num_layers": num_layers,
        "dropout": dropout,
        "seq_len": seq_len,
        "feature_names": feature_names,
        "label_col": label_col,
        "best_epoch": best_epoch,
        "valid_ic": best_ic,
        "test_ic": test_ic,
        "saved_at": datetime.now().isoformat(),
    }, full_path)
    print(f"[GRU] 模型已保存: {full_path}")

    return model, best_ic, test_ic


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--lite", action="store_true", help="用 factors_latest.parquet 快速验证（近3个月）")
    args = parser.parse_args()

    if args.lite:
        from qlib_bridge.adapter import _QUANT_ROOT
        lite_path = str(_QUANT_ROOT / "data" / "factors_latest.parquet")
        print(f"[GRU] LITE 模式: {lite_path}")
        # lite 数据只有 2025-11 至今，缩短训练/验证窗口
        import qlib_bridge.adapter as _adp
        _orig_init = _adp.QuantDataAdapter.__init__
        def _lite_init(self, factors_path=None, label_col=_adp.DEFAULT_LABEL):
            _orig_init(self, factors_path=lite_path, label_col=label_col)
        _adp.QuantDataAdapter.__init__ = _lite_init

        train(
            seq_len=5, n_epochs=20, early_stop=5,
            save_path="ml/model_store/v1/gru_model_lite.pt",
            train_start="2025-11-01", train_end="2025-12-31",
            valid_start="2026-01-01", valid_end="2026-02-15",
            test_start="2026-02-16",  test_end="2026-03-13",
        )
    else:
        train()
