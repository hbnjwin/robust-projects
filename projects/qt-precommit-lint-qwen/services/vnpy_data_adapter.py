"""
VNPy 数据适配器 — Phase 1
将 PG daily_price 导出为 VNPy AlphaLab 格式 (每只股票一个 Parquet)

ts_code 格式转换:
  000001.SZ → 000001.SZSE
  600000.SH → 600000.SSE
  920305.BJ → 920305.BSE

VNPy BarData Parquet 格式:
  datetime, open, high, low, close, volume, turnover, open_interest
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import polars as pl
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import PG_CONFIG

# ── 配置 ──
LAB_PATH = Path("/home/tulin/quant/vnpy_lab")
DAILY_PATH = LAB_PATH / "daily"
CONTRACT_PATH = LAB_PATH / "contract.json"

# 交易所映射: Tushare → VNPy Exchange
EXCHANGE_MAP = {
    "SZ": "SZSE",
    "SH": "SSE",
    "BJ": "BSE",
}

# A股默认合约参数
DEFAULT_CONTRACT = {
    "long_rate": 0.0003,  # 买入手续费 0.03%
    "short_rate": 0.0013,  # 卖出手续费 0.13% (含印花税0.1%)
    "size": 1,  # 合约乘数 (股票=1)
    "pricetick": 0.01,  # 最小变动价位
}


def ts_to_vnpy(ts_code: str) -> str:
    """000001.SZ → 000001.SZSE"""
    symbol, exchange = ts_code.split(".")
    vnpy_exchange = EXCHANGE_MAP.get(exchange, exchange)
    return f"{symbol}.{vnpy_exchange}"


def export_all_stocks():
    """导出全部股票日线到 VNPy Parquet 格式"""
    conn = psycopg.connect(**PG_CONFIG)
    cur = conn.cursor()

    # 获取所有股票代码
    cur.execute("SELECT DISTINCT ts_code FROM daily_price ORDER BY ts_code")
    all_codes = [r[0] for r in cur.fetchall()]
    print(f"[vnpy_adapter] Total stocks: {len(all_codes)}")

    contracts = {}
    exported = 0
    skipped = 0
    start_time = time.time()

    for i, ts_code in enumerate(all_codes):
        vt_symbol = ts_to_vnpy(ts_code)

        # 查询该股票全部日线
        cur.execute(
            """
            SELECT trade_date, open, high, low, close, vol
            FROM daily_price
            WHERE ts_code = %s
            ORDER BY trade_date
        """,
            (ts_code,),
        )
        rows = cur.fetchall()

        if len(rows) < 10:
            skipped += 1
            continue

        # 构建 Polars DataFrame
        data = {
            "datetime": [datetime(r[0].year, r[0].month, r[0].day) for r in rows],
            "open": [float(r[1] or 0) for r in rows],
            "high": [float(r[2] or 0) for r in rows],
            "low": [float(r[3] or 0) for r in rows],
            "close": [float(r[4] or 0) for r in rows],
            "volume": [float(r[5] or 0) for r in rows],
            "turnover": [0.0] * len(rows),  # PG 没有 turnover, 填 0
            "open_interest": [0.0] * len(rows),  # 股票无持仓量
        }

        df = pl.DataFrame(data)

        # 写入 Parquet
        out_path = DAILY_PATH / f"{vt_symbol}.parquet"
        df.write_parquet(out_path)

        # 记录合约信息
        contracts[vt_symbol] = DEFAULT_CONTRACT.copy()

        exported += 1
        if (i + 1) % 500 == 0:
            elapsed = time.time() - start_time
            print(f"  [{i + 1}/{len(all_codes)}] exported={exported} skipped={skipped} ({elapsed:.1f}s)")

    conn.close()

    # 保存 contract.json
    with open(CONTRACT_PATH, "w") as f:
        json.dump(contracts, f, indent=2, ensure_ascii=False)

    elapsed = time.time() - start_time
    print(f"\n[vnpy_adapter] Done in {elapsed:.1f}s")
    print(f"  Exported: {exported} stocks")
    print(f"  Skipped: {skipped} stocks (< 10 rows)")
    print(f"  Contract: {CONTRACT_PATH}")
    print(f"  Daily dir: {DAILY_PATH}")

    return exported


def verify_export():
    """验证导出结果"""
    parquet_files = list(DAILY_PATH.glob("*.parquet"))
    print(f"\n[verify] Parquet files: {len(parquet_files)}")

    # 抽样检查
    samples = ["000001.SZSE", "600000.SSE", "300750.SZSE"]
    for vt_symbol in samples:
        path = DAILY_PATH / f"{vt_symbol}.parquet"
        if path.exists():
            df = pl.read_parquet(path)
            print(f"  {vt_symbol}: {len(df)} rows, {df['datetime'].min()} ~ {df['datetime'].max()}")
            print(f"    columns: {df.columns}")
            print(f"    sample: {df.tail(1)}")
        else:
            print(f"  {vt_symbol}: NOT FOUND")

    # 验证 AlphaLab 能否读取
    try:
        sys.path.insert(0, "/home/tulin/quant/vnpy")
        from vnpy.alpha import AlphaLab
        from vnpy.trader.constant import Interval

        lab = AlphaLab(str(LAB_PATH))
        bars = lab.load_bar_data("000001.SZSE", Interval.DAILY, "2025-01-01", "2025-12-31")
        print(f"\n  AlphaLab.load_bar_data('000001.SZSE'): {len(bars)} bars")
        if bars:
            b = bars[-1]
            print(
                f"    Last bar: {b.datetime} O={b.open_price} H={b.high_price} L={b.low_price} C={b.close_price} V={b.volume}"
            )
        print("  ✅ AlphaLab verification PASSED")
    except Exception as e:
        print(f"  ❌ AlphaLab verification FAILED: {e}")


if __name__ == "__main__":
    export_all_stocks()
    verify_export()
