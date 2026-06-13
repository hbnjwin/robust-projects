import psycopg
import pandas as pd
import duckdb
import io

from config import PG_CONFIG

FACTOR_IDS = {"MA_DIFF_5_21": 1, "MOM_60": 2, "VOL_20": 3, "VOL_RATIO_20": 4}


def copy_factor(pg_conn, df):
    if df.empty:
        return

    buffer = io.StringIO()
    df.to_csv(buffer, index=False, header=False)
    buffer.seek(0)

    with pg_conn.cursor() as cur:
        cur.copy(
            """
            COPY factor_values (trade_date, ts_code, factor_id, value)
            FROM STDIN WITH CSV
            """,
            buffer,
        )
    pg_conn.commit()


def run():
    pg_conn = psycopg.connect(**PG_CONFIG)

    # 获取全部股票列表
    with pg_conn.cursor() as cur:
        cur.execute("SELECT DISTINCT ts_code FROM daily_price;")
        stocks = [r[0] for r in cur.fetchall()]

    print(f"Total stocks: {len(stocks)}")

    for idx, ts_code in enumerate(stocks):
        df = pd.read_sql(
            "SELECT trade_date, ts_code, close, vol FROM daily_price WHERE ts_code=%s ORDER BY trade_date",
            pg_conn,
            params=(ts_code,),
        )

        if df.empty:
            continue

        con = duckdb.connect()
        con.register("price_data", df)

        query = """
        WITH base AS (
            SELECT
                trade_date,
                ts_code,
                close,
                vol,
                close / NULLIF(LAG(close) OVER (ORDER BY trade_date), 0) - 1 AS daily_return,
                LAG(close, 60) OVER (ORDER BY trade_date) AS close_60ago
            FROM price_data
        )
        SELECT
            trade_date,
            ts_code,
            close,
            vol,
            AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS ma5,
            AVG(close) OVER (ORDER BY trade_date ROWS BETWEEN 20 PRECEDING AND CURRENT ROW) AS ma21,
            STDDEV(daily_return) OVER (ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol20,
            AVG(vol) OVER (ORDER BY trade_date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_ma20,
            CASE WHEN close_60ago > 0 THEN close / close_60ago - 1 ELSE NULL END AS mom60
        FROM base
        """

        factor_df = con.execute(query).fetchdf()
        con.close()

        # 写入每个因子
        for name, fid in FACTOR_IDS.items():
            out = factor_df[["trade_date", "ts_code"]].copy()
            out["factor_id"] = fid

            if name == "MA_DIFF_5_21":
                out["value"] = factor_df["ma5"] - factor_df["ma21"]
            elif name == "MOM_60":
                out["value"] = factor_df["mom60"]
            elif name == "VOL_20":
                out["value"] = factor_df["vol20"]
            elif name == "VOL_RATIO_20":
                out["value"] = factor_df["vol"] / factor_df["vol_ma20"]

            out = out.dropna()
            copy_factor(pg_conn, out)

        if idx % 100 == 0:
            print(f"Processed {idx}/{len(stocks)} stocks")

    pg_conn.close()
    print("✅ Core factors build complete")


if __name__ == "__main__":
    run()
