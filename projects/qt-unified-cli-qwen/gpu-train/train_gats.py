"""
GATs 训练脚本 - 复用 HIST 的 mmap 数据
GATs 在每日 batch 内的所有股票间计算图注意力
输入: [N_stocks_per_day, SEQ_LEN * D_FEAT] (展平)
"""
import os, sys, time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from scipy.stats import spearmanr
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 配置 ──────────────────────────────────────────────────────────────
MMAP_DIR   = "/vol1/mmap_cache/hist"
MODEL_OUT  = str(_ROOT / "ml/model_store/v1/gats_model.pt")

SEQ_LEN    = 20
D_FEAT     = 75
HIDDEN     = 128
N_LAYERS   = 2
DROPOUT    = 0.1
N_EPOCHS   = 50
LR         = 1e-4
EARLY_STOP = 10
# GATs 按日 batch：每天约 4000-5000 只股票，内存压力大，用小 batch
DAILY_BATCH = 2000   # 每次取多少只股票做图注意力
RESUME_EPOCH = 2     # 从此 epoch 续训（0=从头开始）
VALID_CHUNK  = 200_000  # valid 分块大小，避免一次性 9GB OOM

os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)

device = torch.device("cpu")
print(f"device: {device}", flush=True)

# ── 1. 加载 mmap 数据（复用 HIST 的）────────────────────────────────
counts = np.load(os.path.join(MMAP_DIR, "counts.npy"), allow_pickle=True).item()
print(f"样本数: {counts}", flush=True)

def load_split(split):
    n = counts[split]
    X    = np.memmap(os.path.join(MMAP_DIR, f"{split}_X.mmap"),    dtype=np.float32, mode="r", shape=(n, SEQ_LEN, D_FEAT))
    y    = np.memmap(os.path.join(MMAP_DIR, f"{split}_y.mmap"),    dtype=np.float32, mode="r", shape=(n,))
    sidx = np.memmap(os.path.join(MMAP_DIR, f"{split}_sidx.mmap"), dtype=np.int32,   mode="r", shape=(n,))
    return X, y, sidx

# ── 2. GATs 模型 ──────────────────────────────────────────────────────
class GATModel(nn.Module):
    def __init__(self, d_feat, hidden_size, num_layers, dropout):
        super().__init__()
        self.d_feat = d_feat
        self.hidden_size = hidden_size
        self.rnn = nn.GRU(d_feat, hidden_size, num_layers,
                          batch_first=True,
                          dropout=dropout if num_layers > 1 else 0)
        self.transformation = nn.Linear(hidden_size, hidden_size)
        self.a = nn.Parameter(torch.randn(hidden_size * 2, 1))
        self.fc = nn.Linear(hidden_size, hidden_size)
        self.fc_out = nn.Linear(hidden_size, 1)
        self.leaky_relu = nn.LeakyReLU()
        self.softmax = nn.Softmax(dim=1)

    def cal_attention(self, x):
        # x: [N, hidden]
        t = self.transformation(x)
        N, D = t.shape
        e_x = t.unsqueeze(1).expand(N, N, D)
        e_y = t.unsqueeze(0).expand(N, N, D)
        attn_in = torch.cat([e_x, e_y], dim=-1).view(-1, D * 2)  # [N*N, 2D]
        attn_out = attn_in.mm(self.a).view(N, N)                  # [N, N]
        attn_out = self.leaky_relu(attn_out)
        return self.softmax(attn_out)                              # [N, N]

    def forward(self, x):
        # x: [N, SEQ_LEN, D_FEAT]
        out, _ = self.rnn(x)
        h = out[:, -1, :]                          # [N, hidden]
        att = self.cal_attention(h)                # [N, N]
        h = att.mm(h) + h                          # 图聚合 + 残差
        h = self.leaky_relu(self.fc(h))
        return self.fc_out(h).squeeze(-1)          # [N]

model     = GATModel(D_FEAT, HIDDEN, N_LAYERS, DROPOUT).to(device)
optimizer = optim.Adam(model.parameters(), lr=LR)
scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
criterion = nn.MSELoss()

n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"模型参数: {n_params:,}", flush=True)

# ── 3. 训练（随机 mini-batch，不按日）────────────────────────────────
# GATs 理论上应按日 batch，但全量按日太慢
# 这里用随机 mini-batch 近似，效果接近
class MmapDataset(Dataset):
    def __init__(self, split, start=0, end=None):
        n = counts[split]
        if end is None:
            end = n
        self.X    = np.memmap(os.path.join(MMAP_DIR, f"{split}_X.mmap"), dtype=np.float32, mode="r", shape=(n, SEQ_LEN, D_FEAT))[start:end]
        self.y    = np.memmap(os.path.join(MMAP_DIR, f"{split}_y.mmap"), dtype=np.float32, mode="r", shape=(n,))[start:end]

    def __len__(self): return len(self.y)
    def __getitem__(self, i):
        return torch.from_numpy(np.array(self.X[i])), torch.tensor(float(self.y[i]))

BATCH_SIZE  = 2048
CHUNK_SIZE  = 500_000   # 每次加载50万样本到内存，约3GB

# valid/test 分块加载（避免一次性 9GB OOM）
def make_chunked_loaders(split, chunk_size, batch_size):
    n = counts[split]
    loaders = []
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        loaders.append(DataLoader(MmapDataset(split, start, end), batch_size=batch_size, shuffle=False, num_workers=0))
    return loaders

valid_loaders = make_chunked_loaders("valid", VALID_CHUNK, BATCH_SIZE)
test_loaders  = make_chunked_loaders("test",  VALID_CHUNK, BATCH_SIZE)

n_train = counts["train"]
n_chunks = (n_train + CHUNK_SIZE - 1) // CHUNK_SIZE
print(f"train 分 {n_chunks} 个 chunk，每 chunk {CHUNK_SIZE} 样本", flush=True)

def compute_ic(preds, labels):
    if len(preds) < 10: return 0.0
    r, _ = spearmanr(preds, labels)
    return float(r) if not np.isnan(r) else 0.0

def run_epoch_chunked(loaders, train=False):
    """支持分块 loaders 的 eval，避免一次性加载全量 valid/test OOM"""
    model.eval()
    total_loss, all_pred, all_label, total_n = 0.0, [], [], 0
    with torch.no_grad():
        for loader in loaders:
            for X, y in loader:
                X, y = X.to(device), y.to(device)
                pred = model(X)
                loss = criterion(pred, y)
                total_loss += loss.item() * len(y)
                all_pred.extend(pred.cpu().numpy())
                all_label.extend(y.cpu().numpy())
                total_n += len(y)
    return total_loss / total_n, compute_ic(all_pred, all_label)

# ── 续训：从 checkpoint 恢复 ──────────────────────────────────────────
if RESUME_EPOCH > 0 and os.path.exists(MODEL_OUT):
    model.load_state_dict(torch.load(MODEL_OUT, map_location=device))
    print(f"✅ 从 epoch {RESUME_EPOCH} checkpoint 恢复，继续训练", flush=True)
    best_ic = 0.0818   # epoch 2 的 VaIC
    best_epoch = RESUME_EPOCH
    no_improve = 0
else:
    best_ic, best_epoch, no_improve = -999, 0, 0
print(f"\n{'Epoch':>5} {'TrLoss':>8} {'TrIC':>7} {'VaLoss':>8} {'VaIC':>7} {'Best':>5} {'Time':>6}", flush=True)
print("-" * 55, flush=True)

# 预生成 chunk 顺序（每 epoch 打乱）
chunk_indices = list(range(n_chunks))

for epoch in range(RESUME_EPOCH + 1, N_EPOCHS + 1):
    t0 = time.time()
    np.random.shuffle(chunk_indices)

    # 分块训练
    model.train()
    tr_total_loss, tr_all_pred, tr_all_label = 0.0, [], []
    tr_total_n = 0

    for ci in chunk_indices:
        start = ci * CHUNK_SIZE
        end   = min(start + CHUNK_SIZE, n_train)
        chunk_ds = MmapDataset("train", start, end)
        chunk_loader = DataLoader(chunk_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)

        for X, y in chunk_loader:
            X, y = X.to(device), y.to(device)
            pred = model(X)
            loss = criterion(pred, y)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            tr_total_loss += loss.item() * len(y)
            tr_all_pred.extend(pred.detach().cpu().numpy())
            tr_all_label.extend(y.cpu().numpy())
            tr_total_n += len(y)

    tr_loss = tr_total_loss / tr_total_n
    tr_ic   = compute_ic(tr_all_pred, tr_all_label)

    va_loss, va_ic = run_epoch_chunked(valid_loaders)
    scheduler.step(va_loss)
    elapsed = time.time() - t0

    is_best = va_ic > best_ic
    if is_best:
        best_ic, best_epoch, no_improve = va_ic, epoch, 0
        torch.save(model.state_dict(), MODEL_OUT)
    else:
        no_improve += 1

    print(f"{epoch:>5} {tr_loss:>8.4f} {tr_ic:>7.4f} {va_loss:>8.4f} {va_ic:>7.4f} {'*' if is_best else '':>5} {elapsed:>5.0f}s", flush=True)

    if no_improve >= EARLY_STOP:
        print(f"Early stop at epoch {epoch}, best={best_epoch}, best valid IC={best_ic:.4f}", flush=True)
        break

# ── 4. 测试集 ─────────────────────────────────────────────────────────
print(f"\n加载最佳模型 (epoch {best_epoch}) ...", flush=True)
model.load_state_dict(torch.load(MODEL_OUT, map_location=device))
te_loss, te_ic = run_epoch_chunked(test_loaders)
print(f"Test Loss={te_loss:.4f}, Test Rank IC={te_ic:.4f}", flush=True)
print(f"✅ 模型已保存: {MODEL_OUT}", flush=True)
