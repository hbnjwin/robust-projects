import psycopg
import pandas as pd

from .base import BaseDAO


class PostgresDAO(BaseDAO):
    def __init__(self, host, port, user, password, dbname):
        self.conn = psycopg.connect(host=host, port=port, user=user, password=password, dbname=dbname)

    def get_daily_price(self, ts_code: str):
        query = """
        SELECT trade_date, open, high, low, close, vol
        FROM daily_price
        WHERE ts_code = %s
        ORDER BY trade_date ASC
        """
        df = pd.read_sql(query, self.conn, params=(ts_code,))
        return df

    def close(self):
        self.conn.close()
