import os
import tushare as ts
import psycopg
from datetime import datetime, timedelta

# 股票池
CODES = ['603019.SH','000977.SZ','002230.SZ','688256.SH']


def get_last_date(pg_conn, ts_code):
    cur = pg_conn.cursor()
    cur.execute(
        "SELECT MAX(trade_date) FROM daily_price WHERE ts_code=%s",
        (ts_code,)
    )
    result = cur.fetchone()[0]
    cur.close()
    return result


def update_one(pg_conn, ts_code):
    token = os.getenv("TUSHARE_TOKEN")
    ts.set_token(token)
    pro = ts.pro_api()

    last_date = get_last_date(pg_conn, ts_code)

    if last_date:
        start_date = (last_date + timedelta(days=1)).strftime("%Y%m%d")
    else:
        start_date = "20160101"

    end_date = datetime.today().strftime("%Y%m%d")

    df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)

    if df.empty:
        print(ts_code, "No new data")
        return 0

    cur = pg_conn.cursor()
    inserted = 0

    for _, row in df.iterrows():
        cur.execute(
            """
            INSERT INTO daily_price (ts_code, trade_date, open, high, low, close, vol)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
            """,
            (
                row['ts_code'],
                datetime.strptime(row['trade_date'], '%Y%m%d').date(),
                row['open'],
                row['high'],
                row['low'],
                row['close'],
                row['vol'],
            ),
        )
        inserted += 1

    pg_conn.commit()
    cur.close()

    print(ts_code, "Inserted:", inserted)
    return inserted


def main():
    pg_conn = psycopg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='limit123',
        dbname='quant'
    )

    total = 0
    for code in CODES:
        total += update_one(pg_conn, code)

    print("Total inserted:", total)
    pg_conn.close()


if __name__ == "__main__":
    main()
