"""
快速行情数据加载器 (CSV/Parquet 版)
从本地年度 CSV 或全量 Parquet 加载，比 PG 快 100x
"""
import os
import duckdb


_CSV_DIR = "data/yearly"
_PARQUET_PATH = "data/daily_price_full.parquet"


def load_market_data_fast(start: str, end: str) -> dict:
    """
    从本地年度 CSV 快速加载行情数据（优先 CSV，fallback Parquet）

    返回格式与 data_loader.load_market_data 完全一致:
    {date_str: {ts_code: {"close": float, "volume": float, "prev_close": float}}}
    """
    con = duckdb.connect()

    # 确定需要加载哪些年份的 CSV
    start_year = int(start[:4])
    end_year = int(end[:4])

    csv_files = []
    for yr in range(start_year, end_year + 1):
        path = os.path.join(_CSV_DIR, f"{yr}.csv")
        if os.path.exists(path):
            csv_files.append(path)

    if csv_files:
        # 从年度 CSV 加载
        union_sql = " UNION ALL ".join(
            f"SELECT * FROM read_csv_auto('{f}')" for f in csv_files
        )
        sql = f"""
            SELECT
                trade_date::VARCHAR AS trade_date,
                ts_code,
                close,
                volume,
                prev_close
            FROM ({union_sql})
            WHERE trade_date BETWEEN '{start}' AND '{end}'
              AND prev_close IS NOT NULL
            ORDER BY trade_date, ts_code
        """
    else:
        # Fallback: 全量 Parquet
        sql = f"""
            SELECT
                trade_date::VARCHAR AS trade_date,
                ts_code,
                close,
                volume,
                prev_close
            FROM '{_PARQUET_PATH}'
            WHERE trade_date BETWEEN '{start}' AND '{end}'
              AND prev_close IS NOT NULL
            ORDER BY trade_date, ts_code
        """

    df = con.execute(sql).fetchdf()
    con.close()

    # 向量化转 dict
    market_data = {}
    for date_str, group in df.groupby("trade_date"):
        codes = group["ts_code"].values
        closes = group["close"].values
        volumes = group["volume"].values
        prev_closes = group["prev_close"].values
        day_dict = {}
        for j in range(len(codes)):
            day_dict[codes[j]] = {
                "close": float(closes[j]),
                "volume": float(volumes[j]),
                "prev_close": float(prev_closes[j]),
            }
        market_data[date_str] = day_dict

    return market_data
