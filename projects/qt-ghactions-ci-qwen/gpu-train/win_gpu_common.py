from __future__ import annotations

import os
import time
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
from scipy.stats import spearmanr
from torch.utils.data import DataLoader, Dataset


class IndexedSequenceDataset(Dataset):
    def __init__(self, stock_data, sample_list, seq_len, extra_keys=None):
        self.stock_data = stock_data
        self.sample_list = sample_list
        self.seq_len = seq_len
        self.extra_keys = extra_keys or []

    def __len__(self):
        return len(self.sample_list)

    def __getitem__(self, idx):
        stock_idx, sample_idx = self.sample_list[idx]
        data = self.stock_data[stock_idx]
        x = data["feat"][sample_idx - self.seq_len : sample_idx]
        y = data["label"][sample_idx]
        extras = [data[key][sample_idx] for key in self.extra_keys]
        return (x, y, *extras)


@dataclass
class RuntimeContext:
    device: torch.device
    pin_memory: bool
    amp_enabled: bool
    amp_dtype: torch.dtype
    scaler: torch.cuda.amp.GradScaler | None


@dataclass
class LoopConfig:
    n_epochs: int
    validate_every: int
    save_ckpt_every: int
    early_stop: int
    model_out: str
    log_file: str
    ckpt_dir: str
    step_log_every: int = 0
    step_log_label: str = ""


@dataclass
class TrainingResult:
    best_ic: float
    best_epoch: int
    start_epoch: int
    has_validated: bool


def compute_ic(preds, labels):
    preds = np.asarray(preds)
    labels = np.asarray(labels)
    mask = ~(np.isnan(preds) | np.isnan(labels))
    if mask.sum() < 10:
        return 0.0
    corr, _ = spearmanr(preds[mask], labels[mask])
    return float(corr) if not np.isnan(corr) else 0.0


def ts2qlib(ts_code):
    code, market = ts_code.split(".")
    return market + code


def get_split_stocks(df, split, train_end, valid_end):
    if split == "train":
        mask = df["trade_date"] <= train_end
    elif split == "valid":
        mask = (df["trade_date"] > train_end) & (df["trade_date"] <= valid_end)
    else:
        mask = df["trade_date"] > valid_end
    return df.loc[mask, "ts_code"].unique().tolist()


def assign_time_split(df, train_end, valid_end):
    train_end_dt = np.datetime64(train_end)
    valid_end_dt = np.datetime64(valid_end)
    trade_dates = df["trade_date"].to_numpy()
    split = np.full(len(df), "", dtype=object)
    split[trade_dates <= train_end_dt] = "train"
    split[(trade_dates > train_end_dt) & (trade_dates <= valid_end_dt)] = "valid"
    split[trade_dates > valid_end_dt] = "test"
    df = df.copy()
    df["split"] = split
    return df


def build_dataloader(dataset, batch_size, shuffle, pin_memory, num_workers):
    worker_count = min(num_workers, os.cpu_count() or 1)
    loader_kwargs = {
        "dataset": dataset,
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": worker_count,
        "pin_memory": pin_memory,
    }
    if worker_count > 0:
        loader_kwargs["persistent_workers"] = True
        loader_kwargs["prefetch_factor"] = 2
    return DataLoader(**loader_kwargs)


def str2bool(value):
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    if value in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def sanitize_run_tag(run_tag):
    if run_tag is None:
        return ""
    tag = str(run_tag).strip()
    if not tag:
        return ""
    safe = []
    for ch in tag:
        if ch.isalnum() or ch in {"-", "_"}:
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("_")


def build_output_paths(model_out, log_file, ckpt_dir, use_mmap_cache, run_tag=""):
    suffix = "mmap" if use_mmap_cache else "inmem"
    tag = sanitize_run_tag(run_tag)
    suffix = f"{suffix}_{tag}" if tag else suffix

    def _with_suffix(path):
        root, ext = os.path.splitext(path)
        return f"{root}_{suffix}{ext}"

    return _with_suffix(model_out), _with_suffix(log_file), f"{ckpt_dir}_{suffix}"


def create_runtime(use_amp):
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pin_memory = device.type == "cuda"
    amp_enabled = use_amp and device.type == "cuda"
    amp_dtype = (
        torch.bfloat16
        if amp_enabled and torch.cuda.is_bf16_supported()
        else torch.float16
    )
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled and amp_dtype == torch.float16)
    return RuntimeContext(
        device=device,
        pin_memory=pin_memory,
        amp_enabled=amp_enabled,
        amp_dtype=amp_dtype,
        scaler=scaler,
    )


def prepare_model(model, runtime, use_compile):
    model = model.to(runtime.device)
    compile_msg = "torch.compile: off"
    if use_compile and hasattr(torch, "compile"):
        try:
            model = torch.compile(model, mode="reduce-overhead")
            compile_msg = "torch.compile: on"
        except Exception as exc:  # pragma: no cover - runtime dependent
            compile_msg = f"torch.compile: off ({exc})"
    return model, compile_msg


def _model_container(model):
    return model._orig_mod if hasattr(model, "_orig_mod") else model


def save_model_state(model, path):
    torch.save(_model_container(model).state_dict(), path)


def load_model_state(model, path, device):
    state = torch.load(path, map_location=device)
    _model_container(model).load_state_dict(state)


def run_epoch(
    model,
    loader,
    criterion,
    runtime,
    batch_adapter: Callable,
    optimizer=None,
    need_ic=True,
    epoch=None,
    step_log_every=0,
    step_log_label="",
):
    is_train = optimizer is not None
    model.train(is_train)

    total_loss = 0.0
    total_seen = 0
    all_pred = [] if need_ic else None
    all_label = [] if need_ic else None
    total_steps = len(loader)
    start_time = time.time()

    with torch.set_grad_enabled(is_train):
        for step_idx, batch in enumerate(loader, start=1):
            model_inputs, target = batch_adapter(batch, runtime.device)
            if not isinstance(model_inputs, (tuple, list)):
                model_inputs = (model_inputs,)

            amp_ctx = (
                torch.autocast(device_type="cuda", dtype=runtime.amp_dtype)
                if runtime.amp_enabled
                else nullcontext()
            )
            with amp_ctx:
                pred = model(*model_inputs)
                loss = criterion(pred, target)

            if is_train:
                optimizer.zero_grad(set_to_none=True)
                if runtime.scaler is not None:
                    runtime.scaler.scale(loss).backward()
                    runtime.scaler.unscale_(optimizer)
                    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    runtime.scaler.step(optimizer)
                    runtime.scaler.update()
                else:
                    loss.backward()
                    nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()

            batch_size = target.size(0)
            total_loss += loss.item() * batch_size
            total_seen += batch_size

            if need_ic:
                all_pred.append(pred.detach().float().cpu())
                all_label.append(target.detach().float().cpu())

            if (
                is_train
                and step_log_every > 0
                and ((step_idx % step_log_every == 0) or (step_idx == total_steps))
            ):
                avg_loss = total_loss / max(total_seen, 1)
                elapsed = time.time() - start_time
                prefix = f"[{step_log_label}] " if step_log_label else ""
                epoch_text = f"epoch {epoch} " if epoch is not None else ""
                print(
                    f"{prefix}{epoch_text}step {step_idx}/{total_steps} "
                    f"loss={avg_loss:.4f} elapsed={elapsed:.0f}s",
                    flush=True,
                )

    epoch_loss = total_loss / len(loader.dataset)
    if not need_ic:
        return epoch_loss, None

    preds = torch.cat(all_pred).numpy()
    labels = torch.cat(all_label).numpy()
    return epoch_loss, compute_ic(preds, labels)


def fit_model(
    model,
    optimizer,
    scheduler,
    criterion,
    runtime,
    train_loader,
    valid_loader,
    batch_adapter,
    loop_config,
    start_epoch=1,
    compute_train_ic=True,
):
    os.makedirs(loop_config.ckpt_dir, exist_ok=True)
    best_ic = -999.0
    best_epoch = 0
    no_improve = 0
    has_validated = False

    print(
        f"\n{'Epoch':>5} {'TrLoss':>8} {'TrIC':>7} {'VaLoss':>8} {'VaIC':>7} {'Best':>5} {'Time':>6}",
        flush=True,
    )
    print("-" * 55, flush=True)

    log_f = open(loop_config.log_file, "a", encoding="utf-8")
    try:
        for epoch in range(start_epoch, loop_config.n_epochs + 1):
            t0 = time.time()
            do_validate = (epoch % loop_config.validate_every == 0) or (epoch == loop_config.n_epochs)

            tr_loss, tr_ic = run_epoch(
                model,
                train_loader,
                criterion,
                runtime,
                batch_adapter,
                optimizer=optimizer,
                need_ic=compute_train_ic,
                epoch=epoch,
                step_log_every=loop_config.step_log_every,
                step_log_label=loop_config.step_log_label,
            )

            va_loss = None
            va_ic = None
            is_best = False

            if do_validate:
                has_validated = True
                va_loss, va_ic = run_epoch(
                    model,
                    valid_loader,
                    criterion,
                    runtime,
                    batch_adapter,
                    optimizer=None,
                    need_ic=True,
                )
                scheduler.step(va_loss)
                is_best = va_ic > best_ic
                if is_best:
                    best_ic = va_ic
                    best_epoch = epoch
                    no_improve = 0
                    save_model_state(model, loop_config.model_out)
                else:
                    no_improve += 1
            else:
                if epoch == start_epoch:
                    save_model_state(model, loop_config.model_out)

            elapsed = time.time() - t0

            if is_best or (epoch % loop_config.save_ckpt_every == 0):
                ckpt_path = os.path.join(loop_config.ckpt_dir, f"epoch_{epoch}.pt")
                save_model_state(model, ckpt_path)

            tr_ic_str = f"{tr_ic:>7.4f}" if tr_ic is not None else "   off"
            va_loss_str = f"{va_loss:>8.4f}" if va_loss is not None else "    skip"
            va_ic_str = f"{va_ic:>7.4f}" if va_ic is not None else "   skip"
            msg = (
                f"{epoch:>5} {tr_loss:>8.4f} {tr_ic_str} "
                f"{va_loss_str} {va_ic_str} "
                f"{'*' if is_best else '':>5} {elapsed:>5.0f}s"
            )
            print(msg, flush=True)
            log_f.write(msg + "\n")
            log_f.flush()

            if do_validate and no_improve >= loop_config.early_stop:
                print(f"Early stop at epoch {epoch}", flush=True)
                break
    finally:
        log_f.close()

    if not has_validated and not os.path.exists(loop_config.model_out):
        save_model_state(model, loop_config.model_out)

    return TrainingResult(
        best_ic=best_ic,
        best_epoch=best_epoch,
        start_epoch=start_epoch,
        has_validated=has_validated,
    )
