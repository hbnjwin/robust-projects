import psycopg
import pandas as pd

from config import PG_CONFIG


def load_market_data(start, end, ts_code=None):
    conn = psycopg.connect(**PG_CONFIG)

    if ts_code:
        query = """
            SELECT
                trade_date,
                ts_code,
                close,
                vol,
                LAG(close) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                ) AS prev_close
            FROM daily_price
            WHERE trade_date BETWEEN %s AND %s
              AND ts_code = %s
            ORDER BY trade_date
        """
        with conn.cursor() as cur:
            cur.execute(query, (start, end, ts_code))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
    else:
        query = """
            SELECT
                trade_date,
                ts_code,
                close,
                vol,
                LAG(close) OVER (
                    PARTITION BY ts_code
                    ORDER BY trade_date
                ) AS prev_close
            FROM daily_price
            WHERE trade_date BETWEEN %s AND %s
            ORDER BY trade_date
        """
        with conn.cursor() as cur:
            cur.execute(query, (start, end))
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
    conn.close()

    df = pd.DataFrame(rows, columns=cols)

    market_data = {}

    for date, group in df.groupby("trade_date"):
        market_data[str(date)] = {}
        for _, row in group.iterrows():
            if pd.isna(row["prev_close"]) or pd.isna(row["vol"]) or pd.isna(row["close"]):
                # 跳过缺失关键字段的行
                continue
            market_data[str(date)][row["ts_code"]] = {
                "close": float(row["close"]),
                "volume": float(row["vol"]),
                "prev_close": float(row["prev_close"]),
            }

    return market_data
