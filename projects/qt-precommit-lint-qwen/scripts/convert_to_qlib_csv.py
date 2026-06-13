"""
把 factors_full.parquet 转成 qlib dump_bin 需要的 CSV 格式

qlib 要求:
- 每只股票一个 CSV 文件，文件名为股票代码（如 SH600000.csv）
- 列: date, open, close, high, low, volume, ... (所有因子)
- date 格式: YYYY-MM-DD
- symbol 格式: SH600000 / SZ000001
"""

import os
import gc
import sys
from datetime import date as _date
from pathlib import Path

import pandas as pd

FACTORS_FULL = "data/factors_full.parquet"
OUTPUT_DIR = "data/qlib_csv"


# ts_code (000001.SZ) → qlib symbol (SZ000001)
def ts_to_qlib(ts_code: str) -> str:
    symbol, market = ts_code.split(".")
    return f"{market}{symbol}"


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 按年加载，避免 OOM
    for year in range(2018, 2027):
        filters = [
            ("trade_date", ">=", _date(year, 1, 1)),
            ("trade_date", "<=", _date(year, 12, 31)),
        ]
        try:
            df = pd.read_parquet(FACTORS_FULL, filters=filters)
        except Exception:
            df = pd.read_parquet(FACTORS_FULL)
            df = df[pd.to_datetime(df["trade_date"]).dt.year == year]

        if df.empty:
            continue

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["symbol"] = df["ts_code"].apply(ts_to_qlib)
        df = df.rename(columns={"trade_date": "date"})
        df = df.drop(columns=["ts_code"], errors="ignore")

        # 按股票追加写入
        for symbol, grp in df.groupby("symbol"):
            grp = grp.sort_values("date")
            grp["date"] = grp["date"].dt.strftime("%Y-%m-%d")
            path = os.path.join(OUTPUT_DIR, f"{symbol}.csv")
            header = not os.path.exists(path)
            grp.drop(columns=["symbol"]).to_csv(path, mode="a", header=header, index=False)

        n_stocks = df["symbol"].nunique()
        print(f"{year}: {len(df)} rows, {n_stocks} stocks")
        del df
        gc.collect()

    # 统计
    files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".csv")]
    print(f"\n总计: {len(files)} 只股票 CSV 文件")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
