import akshare as ak, pandas as pd
from pathlib import Path

df = ak.stock_info_a_code_name()
df["ts_code"] = df["code"].apply(lambda x: x + ".SH" if x.startswith("6") else x + ".SZ")
df = df[["ts_code", "name"]]
csv = "/home/tulin/quant/data/stock_list.csv"
if Path(csv).exists():
    old = pd.read_csv(csv)
    etf = old[old["ts_code"].str.split(".").str[0].str.match(r"^(1[0-5]|5[0-8]|56)")]
    df = pd.concat([df, etf], ignore_index=True).drop_duplicates("ts_code")
df.to_csv(csv, index=False)
print(f"stock_list OK: {len(df)}")
