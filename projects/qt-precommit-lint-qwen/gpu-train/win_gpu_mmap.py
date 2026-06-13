from __future__ import annotations

import json
import os

import numpy as np
import torch
from torch.utils.data import Dataset


SPLITS = ("train", "valid", "test")


def _meta_path(cache_dir):
    return os.path.join(cache_dir, "meta.json")


def build_sequence_mmap_cache(
    df,
    feat_cols,
    label_col,
    seq_len,
    cache_dir,
    extra_columns=None,
    force_rebuild=False,
):
    extra_columns = extra_columns or []
    os.makedirs(cache_dir, exist_ok=True)
    meta_path = _meta_path(cache_dir)

    if os.path.exists(meta_path) and not force_rebuild:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if "split" not in df.columns:
        raise ValueError("Dataframe must contain a 'split' column before building mmap cache")

    counts = {split: 0 for split in SPLITS}
    for _, grp in df.groupby("ts_code", sort=False):
        split_arr = grp["split"].to_numpy()
        for i in range(seq_len, len(grp)):
            split = split_arr[i]
            if split in counts:
                counts[split] += 1

    x_mmaps = {
        split: np.memmap(
            os.path.join(cache_dir, f"{split}_X.mmap"),
            dtype=np.float32,
            mode="w+",
            shape=(counts[split], seq_len, len(feat_cols)),
        )
        for split in SPLITS
    }
    y_mmaps = {
        split: np.memmap(
            os.path.join(cache_dir, f"{split}_y.mmap"),
            dtype=np.float32,
            mode="w+",
            shape=(counts[split],),
        )
        for split in SPLITS
    }
    extra_mmaps = {
        split: {
            col: np.memmap(
                os.path.join(cache_dir, f"{split}_{col}.mmap"),
                dtype=np.int32,
                mode="w+",
                shape=(counts[split],),
            )
            for col in extra_columns
        }
        for split in SPLITS
    }
    ptrs = {split: 0 for split in SPLITS}

    for _, grp in df.groupby("ts_code", sort=False):
        feat = np.array(
            np.nan_to_num(grp[feat_cols].to_numpy(dtype=np.float32, copy=False), nan=0.0),
            dtype=np.float32,
            order="C",
            copy=True,
        )
        label = np.array(
            grp[label_col].to_numpy(dtype=np.float32, copy=False),
            dtype=np.float32,
            order="C",
            copy=True,
        )
        extras = {
            col: np.array(
                grp[col].to_numpy(dtype=np.int32, copy=False),
                dtype=np.int32,
                order="C",
                copy=True,
            )
            for col in extra_columns
        }
        split_arr = grp["split"].to_numpy()

        for i in range(seq_len, len(grp)):
            split = split_arr[i]
            if split not in ptrs:
                continue
            p = ptrs[split]
            x_mmaps[split][p] = feat[i - seq_len : i]
            y_mmaps[split][p] = label[i]
            for col in extra_columns:
                extra_mmaps[split][col][p] = extras[col][i]
            ptrs[split] += 1

    for split in SPLITS:
        x_mmaps[split].flush()
        y_mmaps[split].flush()
        for col in extra_columns:
            extra_mmaps[split][col].flush()

    meta = {
        "counts": counts,
        "seq_len": seq_len,
        "d_feat": len(feat_cols),
        "extra_columns": extra_columns,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=True, indent=2)
    return meta


class SequenceMemmapDataset(Dataset):
    def __init__(self, cache_dir, split):
        with open(_meta_path(cache_dir), "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.cache_dir = cache_dir
        self.split = split
        self.count = meta["counts"][split]
        self.seq_len = meta["seq_len"]
        self.d_feat = meta["d_feat"]
        self.extra_columns = list(meta.get("extra_columns", []))
        self._x_path = os.path.join(cache_dir, f"{split}_X.mmap")
        self._y_path = os.path.join(cache_dir, f"{split}_y.mmap")
        self._extra_paths = {col: os.path.join(cache_dir, f"{split}_{col}.mmap") for col in self.extra_columns}
        self.X = None
        self.y = None
        self.extras = None

    def _ensure_open(self):
        if self.X is not None:
            return
        self.X = np.memmap(
            self._x_path,
            dtype=np.float32,
            mode="r",
            shape=(self.count, self.seq_len, self.d_feat),
        )
        self.y = np.memmap(
            self._y_path,
            dtype=np.float32,
            mode="r",
            shape=(self.count,),
        )
        self.extras = {
            col: np.memmap(
                path,
                dtype=np.int32,
                mode="r",
                shape=(self.count,),
            )
            for col, path in self._extra_paths.items()
        }

    def __len__(self):
        return self.count

    def __getitem__(self, idx):
        self._ensure_open()
        x = torch.from_numpy(np.array(self.X[idx], dtype=np.float32, copy=True))
        y = torch.tensor(float(self.y[idx]), dtype=torch.float32)
        extras = [torch.tensor(int(self.extras[col][idx]), dtype=torch.long) for col in self.extra_columns]
        return (x, y, *extras)
