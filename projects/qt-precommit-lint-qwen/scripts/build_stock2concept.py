"""
构建 HIST 模型所需的 stock2concept.npy 和 stock_index.npy
数据来源：akshare 申万一级行业成分股 (index_component_sw)
"""

import os, time
import numpy as np
import pandas as pd
import akshare as ak

OUT_DIR = "/vol1/qlib_data/stock2concept"
os.makedirs(OUT_DIR, exist_ok=True)

# 申万一级行业代码（2021版，31个）
SW_L1 = {
    "801010": "农林牧渔",
    "801020": "采掘",
    "801030": "化工",
    "801040": "钢铁",
    "801050": "有色金属",
    "801080": "电子",
    "801110": "家用电器",
    "801120": "食品饮料",
    "801130": "纺织服装",
    "801140": "轻工制造",
    "801150": "医药生物",
    "801160": "公用事业",
    "801170": "交通运输",
    "801180": "房地产",
    "801200": "商业贸易",
    "801210": "休闲服务",
    "801230": "综合",
    "801710": "建筑材料",
    "801720": "建筑装饰",
    "801730": "电气设备",
    "801740": "国防军工",
    "801750": "计算机",
    "801760": "传媒",
    "801770": "通信",
    "801780": "银行",
    "801790": "非银金融",
    "801880": "汽车",
    "801890": "机械设备",
    "801950": "煤炭",
    "801960": "石油石化",
    "801970": "环保",
    "801980": "美容护理",
}

# ── 1. 读取 qlib instruments ──────────────────────────────────────────
inst_file = "/vol1/qlib_data/instruments/all.txt"
qlib_stocks = set()
with open(inst_file) as f:
    for line in f:
        parts = line.strip().split("\t")
        if parts:
            qlib_stocks.add(parts[0])
print(f"qlib instruments: {len(qlib_stocks)}")


def ts2qlib(ts_code):
    """000001.SZ -> SZ000001"""
    code, mkt = ts_code.split(".")
    return mkt + code


# ── 2. 逐行业拉取成分股 ───────────────────────────────────────────────
records = []
for sw_code, sw_name in SW_L1.items():
    try:
        df = ak.index_component_sw(symbol=sw_code)
        for _, row in df.iterrows():
            ts_code = str(row["证券代码"]).zfill(6)
            # 判断市场
            if ts_code.startswith("6"):
                qlib_code = "SH" + ts_code
            elif ts_code.startswith(("0", "3")):
                qlib_code = "SZ" + ts_code
            elif ts_code.startswith(("4", "8", "9")):
                qlib_code = "BJ" + ts_code
            else:
                continue
            records.append({"qlib_code": qlib_code, "industry": sw_name, "sw_code": sw_code})
        print(f"  {sw_name}({sw_code}): {len(df)} 只")
        time.sleep(0.3)
    except Exception as e:
        print(f"  {sw_name}({sw_code}) 失败: {e}")

df_map = pd.DataFrame(records).drop_duplicates("qlib_code")
print(f"\n总计: {len(df_map)} 只股票, {df_map.industry.nunique()} 个行业")

# 只保留 qlib 里有的
df_map = df_map[df_map["qlib_code"].isin(qlib_stocks)].copy()
print(f"匹配 qlib: {len(df_map)} 只")

# ── 3. 构建矩阵 ───────────────────────────────────────────────────────
industries = sorted(df_map["industry"].unique())
concept2idx = {c: i for i, c in enumerate(industries)}
N_concepts = len(industries)

stocks = sorted(df_map["qlib_code"].unique())
stock2idx = {s: i for i, s in enumerate(stocks)}
N_stocks = len(stocks)

# [N_stocks+1, N_concepts]，最后一行全0作为 unknown 占位
matrix = np.zeros((N_stocks + 1, N_concepts), dtype=np.float32)
for _, row in df_map.iterrows():
    si = stock2idx[row["qlib_code"]]
    ci = concept2idx[row["industry"]]
    matrix[si, ci] = 1.0

print(f"matrix shape: {matrix.shape}, 有行业的股票: {(matrix.sum(1) > 0).sum()}")

# ── 4. 保存 ───────────────────────────────────────────────────────────
s2c_path = os.path.join(OUT_DIR, "stock2concept.npy")
sidx_path = os.path.join(OUT_DIR, "stock_index.npy")
np.save(s2c_path, matrix)
np.save(sidx_path, stock2idx)

# 保存行业列表供参考
pd.DataFrame({"id": range(N_concepts), "name": industries}).to_csv(
    os.path.join(OUT_DIR, "concept_list.csv"), index=False
)
df_map.to_csv(os.path.join(OUT_DIR, "stock2industry.csv"), index=False)

print(f"\n✅ 完成:")
print(f"  {s2c_path}  shape={matrix.shape}")
print(f"  {sidx_path}  stocks={len(stock2idx)}")

# ── 5. 快速验证 ───────────────────────────────────────────────────────
m = np.load(s2c_path)
idx = np.load(sidx_path, allow_pickle=True).item()
for code in ["SH600000", "SZ000001", "SZ000858"]:
    if code in idx:
        i = idx[code]
        c = [industries[j] for j in np.where(m[i] > 0)[0]]
        print(f"  {code} -> {c}")
