"""
HIST 训练脚本 v2 - mmap 流式 Dataset，避免 OOM
- 先把所有样本写成 mmap 文件（一次性，后续可复用）
- Dataset 按需读取，内存占用恒定
"""
import os, sys, time
from datetime import date
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from scipy.stats import spearmanr

# ── 配置 ──────────────────────────────────────────────────────────────
FACTORS_PATH = "/home/tulin/quant/data/factors_full.parquet"
S2C_PATH     = "/vol1/qlib_data/stock2concept/stock2concept.npy"
SIDX_PATH    = "/vol1/qlib_data/stock2concept/stock_index.npy"
MODEL_OUT    = "/home/tulin/quant/ml/model_store/v1/hist_model.pt"
MMAP_DIR     = "/vol1/mmap_cache/hist"

TRAIN_END    = "2022-12-31"
VALID_START  = "2023-01-01"
VALID_END    = "2024-06-30"
TEST_START   = "2024-07-01"

SEQ_LEN      = 20
D_FEAT       = 75
HIDDEN       = 128
N_LAYERS     = 2
DROPOUT      = 0.1
N_EPOCHS     = 50
RESUME_EPOCH = int(os.environ.get("RESUME_EPOCH", "0"))   # 0=从头，>0=从第N轮续
CKPT_DIR     = "/home/tulin/quant/ml/model_store/v1_checkpoints"
LR           = 1e-4
BATCH_SIZE   = 1024
EARLY_STOP   = 10
LABEL_COL    = "label_5d"

os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
os.makedirs(CKPT_DIR, exist_ok=True)
os.makedirs(MMAP_DIR, exist_ok=True)

device = torch.device("cpu")
print(f"device: {device}", flush=True)

# ── 1. 加载 stock2concept ─────────────────────────────────────────────
print("加载 stock2concept ...", flush=True)
s2c_matrix  = np.load(S2C_PATH)
stock_index = np.load(SIDX_PATH, allow_pickle=True).item()
N_CONCEPTS  = s2c_matrix.shape[1]
UNKNOWN_IDX = s2c_matrix.shape[0] - 1
print(f"  s2c: {s2c_matrix.shape}, concepts: {N_CONCEPTS}", flush=True)

def ts2qlib(ts_code):
    code, mkt = ts_code.split(".")
    return mkt + code

# ── 2. 构建 mmap 文件（如已存在则跳过）────────────────────────────────
SPLIT_NAMES = ["train", "valid", "test"]
SPLIT_ENDS  = {
    "train": np.datetime64(TRAIN_END),
    "valid": np.datetime64(VALID_END),
    "test":  np.datetime64("2026-12-31"),
}
SPLIT_STARTS = {
    "train": np.datetime64("2000-01-01"),
    "valid": np.datetime64(VALID_START),
    "test":  np.datetime64(TEST_START),
}

mmap_x_paths    = {s: os.path.join(MMAP_DIR, f"{s}_X.mmap")    for s in SPLIT_NAMES}
mmap_y_paths    = {s: os.path.join(MMAP_DIR, f"{s}_y.mmap")    for s in SPLIT_NAMES}
mmap_sidx_paths = {s: os.path.join(MMAP_DIR, f"{s}_sidx.mmap") for s in SPLIT_NAMES}
count_path      = os.path.join(MMAP_DIR, "counts.npy")

need_build = not os.path.exists(count_path)
if not need_build:
    counts = np.load(count_path, allow_pickle=True).item()
    for s in SPLIT_NAMES:
        if not os.path.exists(mmap_x_paths[s]):
            need_build = True
            break

if need_build:
    print("构建 mmap 样本文件 ...", flush=True)

    # 先扫描一遍统计各 split 的样本数
    print("  第一遍：统计样本数 ...", flush=True)
    counts = {s: 0 for s in SPLIT_NAMES}
    feat_cols = None

    for year in range(2018, 2026):
        cache = os.path.join(MMAP_DIR, f"factors_{year}.parquet")
        if os.path.exists(cache):
            df_y = pd.read_parquet(cache)
        else:
            df_y = pd.read_parquet(FACTORS_PATH,
                filters=[("trade_date", ">=", date(year, 1, 1)),
                         ("trade_date", "<=", date(year, 12, 31))])
            df_y.to_parquet(cache)
        if feat_cols is None:
            feat_cols = [c for c in df_y.columns
                         if c not in ["ts_code", "trade_date", "label_10d", "label_3d", "label_5d"]]

        df_y["trade_date"] = pd.to_datetime(df_y["trade_date"])
        df_y = df_y.sort_values(["ts_code", "trade_date"])

        for code, grp in df_y.groupby("ts_code", sort=False):
            label = grp[LABEL_COL].values
            dates = grp["trade_date"].values.astype("datetime64[D]")
            for i in range(SEQ_LEN, len(grp)):
                if np.isnan(label[i]):
                    continue
                d = dates[i]
                for s in SPLIT_NAMES:
                    if SPLIT_STARTS[s] <= d <= SPLIT_ENDS[s]:
                        counts[s] += 1
                        break
        print(f"  {year} done, counts so far: {counts}", flush=True)

    print(f"  样本数: {counts}", flush=True)
    np.save(count_path, counts)

    # 分配 mmap
    mmaps_X    = {s: np.memmap(mmap_x_paths[s],    dtype=np.float32, mode="w+",
                               shape=(counts[s], SEQ_LEN, D_FEAT)) for s in SPLIT_NAMES}
    mmaps_y    = {s: np.memmap(mmap_y_paths[s],    dtype=np.float32, mode="w+",
                               shape=(counts[s],)) for s in SPLIT_NAMES}
    mmaps_sidx = {s: np.memmap(mmap_sidx_paths[s], dtype=np.int32,   mode="w+",
                               shape=(counts[s],)) for s in SPLIT_NAMES}
    ptrs = {s: 0 for s in SPLIT_NAMES}

    print("  第二遍：写入 mmap ...", flush=True)
    for year in range(2018, 2026):
        cache = os.path.join(MMAP_DIR, f"factors_{year}.parquet")
        df_y = pd.read_parquet(cache)
        df_y["trade_date"] = pd.to_datetime(df_y["trade_date"])
        df_y = df_y.sort_values(["ts_code", "trade_date"])
        df_y["qlib_code"] = df_y["ts_code"].apply(ts2qlib)
        df_y["stock_idx"] = df_y["qlib_code"].map(stock_index).fillna(UNKNOWN_IDX).astype(int)

        for code, grp in df_y.groupby("ts_code", sort=False):
            feat  = np.nan_to_num(grp[feat_cols].values.astype(np.float32), nan=0.0)
            label = grp[LABEL_COL].values.astype(np.float32)
            sidx  = grp["stock_idx"].values.astype(np.int32)
            dates = grp["trade_date"].values.astype("datetime64[D]")

            for i in range(SEQ_LEN, len(grp)):
                if np.isnan(label[i]):
                    continue
                d = dates[i]
                for s in SPLIT_NAMES:
                    if SPLIT_STARTS[s] <= d <= SPLIT_ENDS[s]:
                        p = ptrs[s]
                        mmaps_X[s][p]    = feat[i-SEQ_LEN:i]
                        mmaps_y[s][p]    = label[i]
                        mmaps_sidx[s][p] = sidx[i]
                        ptrs[s] += 1
                        break

        print(f"  {year} written, ptrs: {ptrs}", flush=True)

    for s in SPLIT_NAMES:
        mmaps_X[s].flush()
        mmaps_y[s].flush()
        mmaps_sidx[s].flush()
    print("  mmap 写入完成", flush=True)

else:
    counts = np.load(count_path, allow_pickle=True).item()
    print(f"  复用已有 mmap，样本数: {counts}", flush=True)

# ── 3. Dataset ────────────────────────────────────────────────────────
class MmapDataset(Dataset):
    def __init__(self, split):
        n = counts[split]
        self.X    = np.memmap(mmap_x_paths[split],    dtype=np.float32, mode="r", shape=(n, SEQ_LEN, D_FEAT))
        self.y    = np.memmap(mmap_y_paths[split],    dtype=np.float32, mode="r", shape=(n,))
        self.sidx = np.memmap(mmap_sidx_paths[split], dtype=np.int32,   mode="r", shape=(n,))

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return (torch.from_numpy(self.X[i].copy()),
                torch.tensor(float(self.y[i])),
                torch.tensor(int(self.sidx[i]), dtype=torch.long))

# ── 是否过滤 unknown 股票（对照实验）────────────────────────────────
FILTER_UNKNOWN = os.environ.get("FILTER_UNKNOWN", "0") == "1"

def make_loader(split, shuffle):
    ds = MmapDataset(split)
    if FILTER_UNKNOWN:
        mask_path = os.path.join(MMAP_DIR, f"{split}_known_mask.npy")
        if os.path.exists(mask_path):
            mask = np.load(mask_path)
            indices = np.where(mask)[0].tolist()
            sampler = torch.utils.data.SubsetRandomSampler(indices) if shuffle \
                      else torch.utils.data.SequentialSampler(
                          torch.utils.data.Subset(ds, indices))
            # Subset + SequentialSampler 更简洁
            ds = torch.utils.data.Subset(ds, indices)
            return DataLoader(ds, batch_size=BATCH_SIZE,
                              shuffle=shuffle, num_workers=4, pin_memory=False)
        else:
            print(f"  [warn] {mask_path} 不存在，不过滤", flush=True)
    return DataLoader(ds, batch_size=BATCH_SIZE,
                      shuffle=shuffle, num_workers=4, pin_memory=False)

train_ds = MmapDataset("train")
valid_ds = MmapDataset("valid")
test_ds  = MmapDataset("test")

train_loader = make_loader("train", shuffle=True)
valid_loader = make_loader("valid", shuffle=False)
test_loader  = make_loader("test",  shuffle=False)

n_train = len(train_loader.dataset)
n_valid = len(valid_loader.dataset)
n_test  = len(test_loader.dataset)
print(f"train={n_train}, valid={n_valid}, test={n_test}", flush=True)
if FILTER_UNKNOWN:
    print(f"  [对照实验] 已过滤 unknown 股票", flush=True)

# ── 4. HIST 模型 ──────────────────────────────────────────────────────
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

model     = HISTModel(D_FEAT, HIDDEN, N_LAYERS, DROPOUT, N_CONCEPTS).to(device)
s2c_t     = torch.from_numpy(s2c_matrix).float().to(device)
optimizer = optim.Adam(model.parameters(), lr=LR)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
criterion = nn.MSELoss()

# ── 5. 训练 ───────────────────────────────────────────────────────────
def compute_ic(preds, labels):
    if len(preds) < 10:
        return 0.0
    r, _ = spearmanr(preds, labels)
    return float(r) if not np.isnan(r) else 0.0

def run_epoch(loader, train=True):
    model.train(train)
    total_loss, all_pred, all_label = 0.0, [], []
    with torch.set_grad_enabled(train):
        for X, y, sidx in loader:
            X, y, sidx = X.to(device), y.to(device), sidx.to(device)
            concept_mat = s2c_t[sidx]
            pred = model(X, concept_mat)
            loss = criterion(pred, y)
            if train:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
            total_loss += loss.item() * len(y)
            all_pred.extend(pred.detach().cpu().numpy())
            all_label.extend(y.cpu().numpy())
    return total_loss / len(loader.dataset), compute_ic(all_pred, all_label)

best_ic, best_epoch, no_improve = -999, 0, 0
start_epoch = 1

if RESUME_EPOCH > 0:
    ckpt = os.path.join(CKPT_DIR, f"epoch_{RESUME_EPOCH}.pt")
    if os.path.exists(ckpt):
        model.load_state_dict(torch.load(ckpt, map_location=device))
        # optimizer 无 checkpoint，从头开始（lr scheduler 也会重置）
        best_ic = -999
        start_epoch = RESUME_EPOCH + 1
        print(f"  断点续训：从 epoch {start_epoch} 继续（已加载 epoch {RESUME_EPOCH} 权重）", flush=True)
    else:
        print(f"  警告：checkpoint {ckpt} 不存在，从头训练", flush=True)

print(f"\n{'Epoch':>5} {'TrLoss':>8} {'TrIC':>7} {'VaLoss':>8} {'VaIC':>7} {'Best':>5} {'Time':>6}", flush=True)
print("-" * 55, flush=True)

for epoch in range(start_epoch, N_EPOCHS + 1):
    t0 = time.time()
    tr_loss, tr_ic = run_epoch(train_loader, train=True)
    va_loss, va_ic = run_epoch(valid_loader, train=False)
    scheduler.step(va_loss)
    elapsed = time.time() - t0

    is_best = va_ic > best_ic
    if is_best:
        best_ic, best_epoch, no_improve = va_ic, epoch, 0
        torch.save(model.state_dict(), MODEL_OUT)
    else:
        no_improve += 1

    # 每轮保存 checkpoint（供断点续训）
    torch.save(model.state_dict(), os.path.join(CKPT_DIR, f"epoch_{epoch}.pt"))
    torch.save(optimizer.state_dict(), os.path.join(CKPT_DIR, f"opt_epoch_{epoch}.pt"))

    print(f"{epoch:>5} {tr_loss:>8.4f} {tr_ic:>7.4f} {va_loss:>8.4f} {va_ic:>7.4f} {'*' if is_best else '':>5} {elapsed:>5.0f}s", flush=True)

    if no_improve >= EARLY_STOP:
        print(f"Early stop at epoch {epoch}, best={best_epoch}, best valid IC={best_ic:.4f}", flush=True)
        break

# ── 6. 测试集 ─────────────────────────────────────────────────────────
print(f"\n加载最佳模型 (epoch {best_epoch}) ...", flush=True)
model.load_state_dict(torch.load(MODEL_OUT, map_location=device))
te_loss, te_ic = run_epoch(test_loader, train=False)
print(f"Test Loss={te_loss:.4f}, Test Rank IC={te_ic:.4f}", flush=True)
print(f"✅ 模型已保存: {MODEL_OUT}", flush=True)
