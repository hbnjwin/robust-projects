"""
GRU training script for Windows GPU.

This version uses the shared Windows GPU framework and supports optional
memmap-backed sequence cache generation/reuse.
"""

import argparse
import os

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim

from win_gpu_common import (
    IndexedSequenceDataset,
    LoopConfig,
    build_output_paths,
    build_dataloader,
    create_runtime,
    fit_model,
    get_split_stocks,
    load_model_state,
    prepare_model,
    run_epoch,
    str2bool,
)
from win_gpu_mmap import SequenceMemmapDataset, build_sequence_mmap_cache

FACTORS_PATH = r"E:\quant_data\factors_full.parquet"
MODEL_OUT = r"E:\quant_data\gru_model.pt"
LOG_FILE = r"E:\quant_data\gru_train.log"
CKPT_DIR = r"E:\quant_data\checkpoints_gru"
MMAP_DIR = r"E:\quant_data\mmap_cache\gru"

SEQ_LEN = 20
D_FEAT = 75
HIDDEN = 64
N_LAYERS = 2
DROPOUT = 0.1
N_EPOCHS = 50
RESUME_EPOCH = 0
LR = 1e-4
BATCH_SIZE = 4096
EARLY_STOP = 10
LABEL_COL = "label_5d"
VALIDATE_EVERY = 2
SAVE_CKPT_EVERY = 5
USE_COMPILE = True
USE_AMP = True
NUM_WORKERS = 8
USE_MMAP_CACHE = True
FORCE_REBUILD_MMAP = False

TRAIN_END = "2022-12-31"
VALID_START = "2023-01-01"
VALID_END = "2024-06-30"
TEST_START = "2024-07-01"


class GRUModel(nn.Module):
    def __init__(self, n_features, hidden_size=64, num_layers=2, dropout=0.1):
        super().__init__()
        self.gru = nn.GRU(
            n_features,
            hidden_size,
            num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
        )

    def forward(self, x):
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


def batch_adapter(batch, device):
    x, y = batch[:2]
    return x.to(device, non_blocking=True), y.to(device, non_blocking=True)


def load_datasets():
    print("Loading factor parquet...", flush=True)
    df_full = pd.read_parquet(FACTORS_PATH)
    df_full["trade_date"] = pd.to_datetime(df_full["trade_date"])
    df_full = df_full.sort_values(["ts_code", "trade_date"])
    df_full = df_full.dropna(subset=[LABEL_COL]).reset_index(drop=True)

    feat_cols = [c for c in df_full.columns if c not in ["ts_code", "trade_date", "label_10d", "label_3d", "label_5d"]]
    if len(feat_cols) != D_FEAT:
        raise ValueError(f"Expected {D_FEAT} features, found {len(feat_cols)}")

    print(f"  data shape: {df_full.shape}, features: {len(feat_cols)}", flush=True)
    train_stocks = get_split_stocks(df_full, "train", TRAIN_END, VALID_END)
    valid_stocks = get_split_stocks(df_full, "valid", TRAIN_END, VALID_END)
    test_stocks = get_split_stocks(df_full, "test", TRAIN_END, VALID_END)
    print(f"  train stocks: {len(train_stocks)}", flush=True)
    print(f"  valid stocks: {len(valid_stocks)}", flush=True)
    print(f"  test stocks:  {len(test_stocks)}", flush=True)

    if USE_MMAP_CACHE:
        print("Building/reusing mmap cache...", flush=True)
        df_cache = df_full.copy()
        train_end_dt = np.datetime64(TRAIN_END)
        valid_end_dt = np.datetime64(VALID_END)
        trade_dates = df_cache["trade_date"].to_numpy()
        split = np.full(len(df_cache), "", dtype=object)
        split[trade_dates <= train_end_dt] = "train"
        split[(trade_dates > train_end_dt) & (trade_dates <= valid_end_dt)] = "valid"
        split[trade_dates > valid_end_dt] = "test"
        df_cache["split"] = split
        meta = build_sequence_mmap_cache(
            df_cache,
            feat_cols,
            LABEL_COL,
            SEQ_LEN,
            MMAP_DIR,
            extra_columns=[],
            force_rebuild=FORCE_REBUILD_MMAP,
        )
        print(f"  mmap counts: {meta['counts']}", flush=True)
        return (
            SequenceMemmapDataset(MMAP_DIR, "train"),
            SequenceMemmapDataset(MMAP_DIR, "valid"),
            SequenceMemmapDataset(MMAP_DIR, "test"),
        )

    stock_data = []
    sample_index = {"train": [], "valid": [], "test": []}
    train_end_dt = np.datetime64(TRAIN_END)
    valid_end_dt = np.datetime64(VALID_END)

    print("Building per-stock tensors and sample index...", flush=True)
    for stock_idx, (_, grp) in enumerate(df_full.groupby("ts_code", sort=False)):
        feat_np = np.array(
            np.nan_to_num(
                grp[feat_cols].to_numpy(dtype=np.float32, copy=False),
                nan=0.0,
            ),
            dtype=np.float32,
            order="C",
            copy=True,
        )
        label_np = np.array(
            grp[LABEL_COL].to_numpy(dtype=np.float32, copy=False),
            dtype=np.float32,
            order="C",
            copy=True,
        )
        dates = grp["trade_date"].to_numpy()

        stock_data.append(
            {
                "feat": torch.from_numpy(feat_np),
                "label": torch.from_numpy(label_np),
            }
        )

        for i in range(SEQ_LEN, len(grp)):
            trade_dt = dates[i]
            if trade_dt <= train_end_dt:
                sample_index["train"].append((stock_idx, i))
            elif trade_dt <= valid_end_dt:
                sample_index["valid"].append((stock_idx, i))
            else:
                sample_index["test"].append((stock_idx, i))

    print(f"  train samples: {len(sample_index['train'])}", flush=True)
    print(f"  valid samples: {len(sample_index['valid'])}", flush=True)
    print(f"  test samples:  {len(sample_index['test'])}", flush=True)
    return (
        IndexedSequenceDataset(stock_data, sample_index["train"], seq_len=SEQ_LEN),
        IndexedSequenceDataset(stock_data, sample_index["valid"], seq_len=SEQ_LEN),
        IndexedSequenceDataset(stock_data, sample_index["test"], seq_len=SEQ_LEN),
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-mmap-cache", type=str2bool, default=USE_MMAP_CACHE)
    parser.add_argument("--run-tag", type=str, default="")
    return parser.parse_args()


def main():
    global USE_MMAP_CACHE

    args = parse_args()
    USE_MMAP_CACHE = args.use_mmap_cache
    model_out, log_file, ckpt_dir = build_output_paths(MODEL_OUT, LOG_FILE, CKPT_DIR, USE_MMAP_CACHE, args.run_tag)

    os.makedirs(ckpt_dir, exist_ok=True)
    runtime = create_runtime(USE_AMP)
    print(f"device: {runtime.device}", flush=True)
    print(f"batch_size: {BATCH_SIZE}", flush=True)
    print(f"use_mmap_cache: {USE_MMAP_CACHE}", flush=True)
    print(f"run_tag: {args.run_tag or '-'}", flush=True)
    print(f"model_out: {model_out}", flush=True)
    print(
        f"amp: {'on' if runtime.amp_enabled else 'off'}"
        + (f" ({str(runtime.amp_dtype).split('.')[-1]})" if runtime.amp_enabled else ""),
        flush=True,
    )

    train_ds, valid_ds, test_ds = load_datasets()
    print("Creating datasets and dataloaders...", flush=True)
    train_loader = build_dataloader(train_ds, BATCH_SIZE, True, runtime.pin_memory, NUM_WORKERS)
    valid_loader = build_dataloader(valid_ds, BATCH_SIZE, False, runtime.pin_memory, NUM_WORKERS)
    test_loader = build_dataloader(test_ds, BATCH_SIZE, False, runtime.pin_memory, NUM_WORKERS)

    model, compile_msg = prepare_model(
        GRUModel(D_FEAT, HIDDEN, N_LAYERS, DROPOUT),
        runtime,
        USE_COMPILE,
    )
    print(compile_msg, flush=True)
    optimizer = optim.Adam(model.parameters(), lr=LR)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    criterion = nn.MSELoss()
    start_epoch = 1

    if RESUME_EPOCH > 0:
        ckpt = os.path.join(ckpt_dir, f"epoch_{RESUME_EPOCH}.pt")
        if os.path.exists(ckpt):
            load_model_state(model, ckpt, runtime.device)
            start_epoch = RESUME_EPOCH + 1
            print(f"Resuming from epoch {start_epoch}", flush=True)

    loop_config = LoopConfig(
        n_epochs=N_EPOCHS,
        validate_every=VALIDATE_EVERY,
        save_ckpt_every=SAVE_CKPT_EVERY,
        early_stop=EARLY_STOP,
        model_out=model_out,
        log_file=log_file,
        ckpt_dir=ckpt_dir,
    )
    result = fit_model(
        model,
        optimizer,
        scheduler,
        criterion,
        runtime,
        train_loader,
        valid_loader,
        batch_adapter,
        loop_config,
        start_epoch=start_epoch,
        compute_train_ic=True,
    )

    load_model_state(model, model_out, runtime.device)
    te_loss, te_ic = run_epoch(
        model,
        test_loader,
        criterion,
        runtime,
        batch_adapter,
        optimizer=None,
        need_ic=True,
    )
    print(f"\nBest epoch={result.best_epoch}, best valid IC={result.best_ic:.4f}", flush=True)
    print(f"Test Loss={te_loss:.4f}, Test Rank IC={te_ic:.4f}", flush=True)
    print(f"Model saved to: {model_out}", flush=True)


if __name__ == "__main__":
    main()
