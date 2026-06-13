"""
GATs vs HIST OOS 对比脚本
在 test split 上对比两个模型的 Rank IC 和回测 Sharpe

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/gats_vs_hist_oos.py
"""

import sys, os, json
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# ── 配置 ──────────────────────────────────────────────────────────────
MMAP_DIR = "/vol1/mmap_cache/hist"
S2C_PATH = "/vol1/qlib_data/stock2concept/stock2concept.npy"
SIDX_PATH = "/vol1/qlib_data/stock2concept/stock_index.npy"
GATS_MODEL = str(_ROOT / "ml/model_store/v1/gats_model.pt")
HIST_MODEL = str(_ROOT / "ml/model_store/v1/hist_model.pt")

SEQ_LEN = 20
D_FEAT = 75
HIDDEN = 128
N_LAYERS = 2
DROPOUT = 0.1
BATCH_SIZE = 2048
device = torch.device("cpu")

# ── 加载 mmap 元数据 ──────────────────────────────────────────────────
counts = np.load(os.path.join(MMAP_DIR, "counts.npy"), allow_pickle=True).item()
n_test = counts["test"]
print(f"test 样本数: {n_test:,}")

X_test = np.memmap(os.path.join(MMAP_DIR, "test_X.mmap"), dtype=np.float32, mode="r", shape=(n_test, SEQ_LEN, D_FEAT))
y_test = np.memmap(os.path.join(MMAP_DIR, "test_y.mmap"), dtype=np.float32, mode="r", shape=(n_test,))
sidx_test = np.memmap(os.path.join(MMAP_DIR, "test_sidx.mmap"), dtype=np.int32, mode="r", shape=(n_test,))

# ── 加载 stock2concept（HIST 需要）────────────────────────────────────
print("加载 stock2concept ...")
s2c_matrix = np.load(S2C_PATH)
N_CONCEPTS = s2c_matrix.shape[1]
s2c_tensor = torch.tensor(s2c_matrix, dtype=torch.float32)


# ── 模型定义 ──────────────────────────────────────────────────────────
class GATModel(nn.Module):
    def __init__(self, d_feat, hidden_size, num_layers, dropout):
        super().__init__()
        self.rnn = nn.GRU(d_feat, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.transformation = nn.Linear(hidden_size, hidden_size)
        self.a = nn.Parameter(torch.randn(hidden_size * 2, 1))
        self.fc = nn.Linear(hidden_size, hidden_size)
        self.fc_out = nn.Linear(hidden_size, 1)
        self.leaky_relu = nn.LeakyReLU()
        self.softmax = nn.Softmax(dim=1)

    def cal_attention(self, x):
        t = self.transformation(x)
        N, D = t.shape
        e_x = t.unsqueeze(1).expand(N, N, D)
        e_y = t.unsqueeze(0).expand(N, N, D)
        attn_in = torch.cat([e_x, e_y], dim=-1).view(-1, D * 2)
        attn_out = self.leaky_relu(attn_in.mm(self.a).view(N, N))
        return self.softmax(attn_out)

    def forward(self, x):
        out, _ = self.rnn(x)
        h = out[:, -1, :]
        att = self.cal_attention(h)
        h = att.mm(h) + h
        h = self.leaky_relu(self.fc(h))
        return self.fc_out(h).squeeze(-1)


class HISTModel(nn.Module):
    def __init__(self, d_feat, hidden_size, num_layers, dropout, n_concepts):
        super().__init__()
        self.rnn = nn.GRU(d_feat, hidden_size, num_layers, batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.concept_fc = nn.Linear(hidden_size, n_concepts)
        self.concept_emb = nn.Linear(n_concepts, hidden_size)
        self.fc_out = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, 1),
        )

    def forward(self, x, concept_matrix):
        out, _ = self.rnn(x)
        h = out[:, -1, :]  # [N, hidden]
        attn = torch.softmax(self.concept_fc(h), dim=-1)  # [N, n_concepts]
        attn = attn * (concept_matrix + 1e-6)
        attn = attn / (attn.sum(dim=-1, keepdim=True) + 1e-8)
        concept_h = self.concept_emb(attn)  # [N, hidden]
        combined = torch.cat([h, concept_h], dim=-1)
        return self.fc_out(combined).squeeze(-1)


# ── 加载模型 ──────────────────────────────────────────────────────────
print("加载 GATs 模型 ...")
gat_model = GATModel(D_FEAT, HIDDEN, N_LAYERS, DROPOUT).to(device)
gat_model.load_state_dict(torch.load(GATS_MODEL, map_location=device))
gat_model.eval()

print("加载 HIST 模型 ...")
hist_model = HISTModel(D_FEAT, HIDDEN, N_LAYERS, DROPOUT, N_CONCEPTS).to(device)
hist_model.load_state_dict(torch.load(HIST_MODEL, map_location=device))
hist_model.eval()


# ── 推理（分批，避免 OOM）────────────────────────────────────────────
class SimpleDataset(Dataset):
    def __init__(self, X, y, sidx):
        self.X = X
        self.y = y
        self.sidx = sidx

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        return torch.tensor(self.X[i]), torch.tensor(self.y[i]), int(self.sidx[i])


print("推理 GATs ...")
gat_preds, labels_all, sidx_all = [], [], []
loader = DataLoader(SimpleDataset(X_test, y_test, sidx_test), batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
with torch.no_grad():
    for X, y, sidx in loader:
        X = X.to(device)
        pred = gat_model(X)
        gat_preds.append(pred.cpu().numpy())
        labels_all.append(y.numpy())
        sidx_all.extend(sidx.tolist())

gat_preds = np.concatenate(gat_preds)
labels_all = np.concatenate(labels_all)
sidx_all = np.array(sidx_all)

print("推理 HIST ...")
hist_preds = []
with torch.no_grad():
    for X, y, sidx in DataLoader(
        SimpleDataset(X_test, y_test, sidx_test), batch_size=BATCH_SIZE, shuffle=False, num_workers=0
    ):
        X = X.to(device)
        sidx_np = sidx.numpy()
        # 取对应的 concept_matrix 行
        cm = s2c_tensor[sidx_np].to(device)
        pred = hist_model(X, cm)
        hist_preds.append(pred.cpu().numpy())

hist_preds = np.concatenate(hist_preds)


# ── 计算 Rank IC ──────────────────────────────────────────────────────
def rank_ic(preds, labels):
    from scipy.stats import spearmanr

    corr, _ = spearmanr(preds, labels)
    return corr


gat_ic = rank_ic(gat_preds, labels_all)
hist_ic = rank_ic(hist_preds, labels_all)

print(f"\n{'=' * 50}")
print(f"Test Rank IC — GATs:  {gat_ic:.4f}")
print(f"Test Rank IC — HIST:  {hist_ic:.4f}")
print(f"{'=' * 50}")

# ── 保存结果 ──────────────────────────────────────────────────────────
out = _ROOT / "data/backtest_compare/gats_vs_hist_oos.json"
out.parent.mkdir(exist_ok=True)
result = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "test_rank_ic": {
        "gats": round(float(gat_ic), 4),
        "hist": round(float(hist_ic), 4),
    },
    "n_test_samples": int(n_test),
}
with open(out, "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"✅ 结果已保存: {out}")
