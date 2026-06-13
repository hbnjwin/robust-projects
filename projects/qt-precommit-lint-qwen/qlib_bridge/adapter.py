"""
qlib_bridge/adapter.py — quant 因子数据 → qlib DatasetH 适配器

内存策略（OOM 修复）：
- 按年分批读取 parquet，每年约 400-600MB
- 滑动窗口结果写入 numpy memmap（磁盘），不在内存累积
- 跨年边界：stock_buffers 保存上年末尾 seq_len-1 行
- 训练时 DataLoader 直接从 memmap 读，内存占用 = 单年数据 + 模型

用法:
    from qlib_bridge.adapter import QuantDataAdapter
    adapter = QuantDataAdapter()
    segs = adapter.build_dataset(...)
    data = adapter.to_numpy(segs, seq_len=20)
    # data["train"] = (X_mmap, y_mmap, idx_list)
    # X_mmap shape: (N, seq_len, n_features)，numpy memmap，可直接传 DataLoader
"""

from __future__ import annotations

import gc
import sys
import tempfile
from datetime import date as _date
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

_QUANT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_QUANT_ROOT))

_SKIP_COLS = {"ts_code", "trade_date", "label_3d", "label_5d", "label_10d", "corr_ret_vol_10", "corr_ret_vol_20"}
DEFAULT_LABEL = "label_5d"

# memmap 缓存目录（训练结束后可手动清理）
_MMAP_DIR = _QUANT_ROOT / "data" / "mmap_cache"


def _ts_to_qlib(ts_code: str) -> str:
    symbol, market = ts_code.split(".")
    return f"{market}{symbol}"


def _qlib_to_ts(instrument: str) -> str:
    return f"{instrument[2:]}.{instrument[:2]}"


def _read_year(path: str, year: int, feature_cols: list[str], label_col: str) -> pd.DataFrame:
    """按年读取 parquet，返回 MultiIndex(instrument, datetime) DataFrame"""
    load_cols = ["ts_code", "trade_date"] + feature_cols + [label_col]
    filters = [
        ("trade_date", ">=", _date(year, 1, 1)),
        ("trade_date", "<=", _date(year, 12, 31)),
    ]
    try:
        raw = pd.read_parquet(path, columns=load_cols, filters=filters)
    except Exception:
        raw = pd.read_parquet(path, columns=load_cols)
        raw = raw[pd.to_datetime(raw["trade_date"]).dt.year == year]

    if raw.empty:
        return pd.DataFrame()

    keep_cols = [c for c in feature_cols + [label_col] if c in raw.columns]
    raw["instrument"] = raw["ts_code"].apply(_ts_to_qlib)
    raw["datetime"] = pd.to_datetime(raw["trade_date"])
    df = raw.set_index(["instrument", "datetime"])[keep_cols].sort_index()
    df = df.dropna(subset=[label_col])
    return df


class QuantDataAdapter:
    def __init__(self, factors_path: str | None = None, label_col: str = DEFAULT_LABEL):
        self.factors_path = factors_path or str(_QUANT_ROOT / "data" / "factors_full.parquet")
        self.label_col = label_col
        self._feature_cols: list[str] | None = None

    def get_feature_names(self) -> list[str]:
        if self._feature_cols is None:
            schema = pq.read_schema(self.factors_path)
            self._feature_cols = [c for c in schema.names if c not in _SKIP_COLS and c != self.label_col]
        return self._feature_cols

    def build_dataset(
        self,
        train_start: str = "2022-01-01",
        train_end: str = "2024-06-30",
        valid_start: str = "2024-07-01",
        valid_end: str = "2025-06-30",
        test_start: str = "2025-07-01",
        test_end: str = "2026-03-13",
    ) -> dict[str, tuple[str, str]]:
        segs = {
            "train": (train_start, train_end),
            "valid": (valid_start, valid_end),
            "test": (test_start, test_end),
        }
        for name, (s, e) in segs.items():
            print(f"[adapter] {name}: {s} ~ {e}")
        return segs

    def to_numpy(
        self,
        segments: dict,
        seq_len: int = 20,
        mmap_dir: str | None = None,
    ) -> dict[str, tuple]:
        """
        按年分批构建滑动窗口，写入 memmap 文件，避免 OOM。

        Returns:
            {split: (X_mmap, y_mmap, idx_list)}
            X_mmap: np.memmap, shape (N, seq_len, n_features), dtype float32
            y_mmap: np.memmap, shape (N,), dtype float32
        """
        feature_cols = self.get_feature_names()
        n_feat = len(feature_cols)
        label_col = self.label_col
        path = self.factors_path

        cache_dir = Path(mmap_dir) if mmap_dir else _MMAP_DIR
        cache_dir.mkdir(parents=True, exist_ok=True)

        result = {}

        for split, seg in segments.items():
            start_date, end_date = seg
            start_year = int(start_date[:4])
            end_year = int(end_date[:4])

            # ── 第一遍：统计总样本数 ──────────────────────────
            print(f"[adapter] {split} 统计样本数...", flush=True)
            total_n = 0
            stock_buffers: dict[str, tuple[np.ndarray, np.ndarray]] = {}

            for year in range(start_year, end_year + 1):
                df_y = _read_year(path, year, feature_cols, label_col)
                if df_y.empty:
                    continue
                dates = df_y.index.get_level_values("datetime")
                df_y = df_y[(dates >= start_date) & (dates <= end_date)]
                if df_y.empty:
                    continue

                n_y, stock_buffers = _count_windows(df_y, seq_len, stock_buffers)
                total_n += n_y
                del df_y
                gc.collect()

            if total_n == 0:
                print(f"[adapter] {split}: 无样本，跳过")
                continue

            print(f"[adapter] {split} 总样本: {total_n:,}", flush=True)

            # ── 创建 memmap ───────────────────────────────────
            X_path = str(cache_dir / f"{split}_X_seq{seq_len}.mmap")
            y_path = str(cache_dir / f"{split}_y_seq{seq_len}.mmap")
            X_mmap = np.memmap(X_path, dtype="float32", mode="w+", shape=(total_n, seq_len, n_feat))
            y_mmap = np.memmap(y_path, dtype="float32", mode="w+", shape=(total_n,))

            # ── 第二遍：写入 memmap ───────────────────────────
            offset = 0
            idx_list: list[str] = []
            stock_buffers = {}

            for year in range(start_year, end_year + 1):
                df_y = _read_year(path, year, feature_cols, label_col)
                if df_y.empty:
                    continue
                dates = df_y.index.get_level_values("datetime")
                df_y = df_y[(dates >= start_date) & (dates <= end_date)]
                if df_y.empty:
                    continue

                X_y, y_y, idx_y, stock_buffers = _build_windows_year(
                    df_y, feature_cols, label_col, seq_len, stock_buffers
                )
                n = len(X_y)
                if n:
                    X_mmap[offset : offset + n] = X_y
                    y_mmap[offset : offset + n] = y_y
                    idx_list.extend(idx_y)
                    offset += n
                    X_mmap.flush()

                del df_y, X_y, y_y
                gc.collect()
                print(f"[adapter] {split} {year} 写入 {n:,} 条，累计 {offset:,}", flush=True)

            # 重新以只读方式打开
            X_mmap = np.memmap(X_path, dtype="float32", mode="r", shape=(total_n, seq_len, n_feat))
            y_mmap = np.memmap(y_path, dtype="float32", mode="r", shape=(total_n,))

            result[split] = (X_mmap, y_mmap, idx_list)
            print(
                f"[adapter] {split} numpy: X={X_mmap.shape} y={y_mmap.shape} ({X_mmap.nbytes / 1024**3:.2f} GB on disk)"
            )

        return result


# ── 辅助函数 ──────────────────────────────────────────────────


def _count_windows(
    df: pd.DataFrame,
    seq_len: int,
    stock_buffers: dict,
) -> tuple[int, dict]:
    """统计滑动窗口数量，同时更新 stock_buffers（跨年边界）"""
    total = 0
    new_buffers = {}
    tail = seq_len - 1

    for instrument, group in df.groupby(level="instrument"):
        group = group.sort_index(level="datetime")
        n_rows = len(group)
        prev_len = len(stock_buffers[instrument][0]) if instrument in stock_buffers else 0
        effective_len = n_rows + prev_len
        total += max(0, effective_len - seq_len)

        feat = group.values[:, :-1].astype(np.float32)  # 最后一列是 label
        lab = group.values[:, -1].astype(np.float32)
        if prev_len:
            pf, pl = stock_buffers[instrument]
            feat = np.concatenate([pf, feat], axis=0)
            lab = np.concatenate([pl, lab], axis=0)
        if len(feat) >= tail:
            new_buffers[instrument] = (feat[-tail:], lab[-tail:])

    return total, new_buffers


def _build_windows_year(
    df_year: pd.DataFrame,
    feature_cols: list[str],
    label_col: str,
    seq_len: int,
    stock_buffers: dict,
) -> tuple[np.ndarray, np.ndarray, list, dict]:
    """对单年数据构建滑动窗口，处理跨年边界"""
    X_list, y_list, idx_list = [], [], []
    new_buffers = {}
    tail = seq_len - 1

    for instrument, group in df_year.groupby(level="instrument"):
        group = group.sort_index(level="datetime")
        features = group[feature_cols].values.astype(np.float32)
        labels = group[label_col].values.astype(np.float32)

        if instrument in stock_buffers:
            pf, pl = stock_buffers[instrument]
            features = np.concatenate([pf, features], axis=0)
            labels = np.concatenate([pl, labels], axis=0)

        for i in range(seq_len, len(features)):
            X_list.append(features[i - seq_len : i])
            y_list.append(labels[i])
            idx_list.append(instrument)

        if len(features) >= tail:
            new_buffers[instrument] = (features[-tail:], labels[-tail:])

    if not X_list:
        empty_X = np.empty((0, seq_len, len(feature_cols)), dtype=np.float32)
        return empty_X, np.empty(0, dtype=np.float32), [], new_buffers

    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float32),
        idx_list,
        new_buffers,
    )
