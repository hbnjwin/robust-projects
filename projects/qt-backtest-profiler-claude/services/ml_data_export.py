"""
增量数据导出
将当日新增的 daily_price 数据追加到年度 CSV + 更新全量 Parquet

调度: 15:12, depends_on: afternoon_sync
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from config import PG_CONFIG

CSV_DIR = "data/yearly"
PARQUET_PATH = "data/daily_price_full.parquet"


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().year
    csv_path = os.path.join(CSV_DIR, f"{year}.csv")

    print(f"[ml_data_export] {today}")

    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres;")

    host = PG_CONFIG["host"]
    if host == "localhost":
        host = "127.0.0.1"
    pg_str = (
        f"dbname={PG_CONFIG['dbname']} "
        f"user={PG_CONFIG['user']} "
        f"password={PG_CONFIG['password']} "
        f"host={host} "
        f"port={PG_CONFIG.get('port', 5432)}"
    )
    con.execute(f"ATTACH '{pg_str}' AS pg (TYPE POSTGRES, READ_ONLY)")

    # 1. 重新导出当年 CSV（覆盖，确保包含最新数据）
    t0 = time.time()
    con.execute(f"""
        COPY (
            SELECT
                trade_date, ts_code, open, high, low, close,
                vol AS volume,
                LAG(close) OVER (PARTITION BY ts_code ORDER BY trade_date) AS prev_close
            FROM pg.public.daily_price
            WHERE EXTRACT(YEAR FROM trade_date) = {year}
            ORDER BY trade_date, ts_code
        ) TO '{csv_path}' (HEADER, DELIMITER ',')
    """)
    rows = con.execute(f"SELECT COUNT(*) FROM '{csv_path}'").fetchone()[0]
    print(f"  CSV {year}: {rows:,} rows ({time.time()-t0:.1f}s)")

    # 2. 重建全量 Parquet（合并所有年度 CSV）
    t1 = time.time()
    csv_files = sorted(Path(CSV_DIR).glob("*.csv"))
    if csv_files:
        union_sql = " UNION ALL ".join(
            f"SELECT * FROM read_csv_auto('{f}')" for f in csv_files
        )
        con.execute(f"""
            COPY (
                SELECT * FROM ({union_sql}) ORDER BY trade_date, ts_code
            ) TO '{PARQUET_PATH}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        total = con.execute(f"SELECT COUNT(*) FROM '{PARQUET_PATH}'").fetchone()[0]
        size_mb = os.path.getsize(PARQUET_PATH) / 1024 / 1024
        print(f"  Parquet: {total:,} rows, {size_mb:.1f} MB ({time.time()-t1:.1f}s)")

    con.close()
    print(f"[ml_data_export] Done")


if __name__ == "__main__":
    main()
