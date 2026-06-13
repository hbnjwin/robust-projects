"""
core/datafeed.py — 数据层抽象接口

支持后端: PostgreSQL / DuckDB(CSV/Parquet) / SQLite / Memory
返回格式统一: {date_str: {ts_code: {"close", "volume", "prev_close"}}}
"""
from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator

_ROOT = Path(__file__).resolve().parent.parent


# ── 抽象基类 ─────────────────────────────────────────────────
class BaseDataFeed(ABC):

    @abstractmethod
    def load_bar_data(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None,
    ) -> dict:
        """返回 {date_str: {ts_code: {close, volume, prev_close}}}"""
        pass

    def iter_bar_data(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None,
    ) -> Iterator[tuple[str, dict]]:
        """流式迭代 (date, prices)，默认一次性加载后迭代"""
        data = self.load_bar_data(start, end, ts_codes)
        for date in sorted(data.keys()):
            yield date, data[date]

    def get_trading_dates(self, start: str, end: str) -> list[str]:
        return sorted(self.load_bar_data(start, end).keys())

    def load_tick_data(self, ts_code: str, start: str, end: str) -> list[dict]:
        raise NotImplementedError(f"{self.__class__.__name__} 不支持 Tick 数据")

    @staticmethod
    def _df_to_dict(df: Any) -> dict:
        """pandas DataFrame → market_data dict"""
        import pandas as pd
        result = {}
        for date, group in df.groupby("trade_date"):
            day = {}
            for _, row in group.iterrows():
                if pd.isna(row.get("prev_close")) or float(row["prev_close"]) <= 0:
                    continue
                day[row["ts_code"]] = {
                    "close":      float(row["close"]),
                    "volume":     float(row["volume"]),
                    "prev_close": float(row["prev_close"]),
                }
            if day:
                result[str(date)] = day
        return result

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ── PostgreSQL 后端 ───────────────────────────────────────────
class PostgresDataFeed(BaseDataFeed):
    """PostgreSQL 数据源"""

    def __init__(self, pg_config: dict | None = None):
        if pg_config is None:
            sys.path.insert(0, str(_ROOT))
            from config import PG_CONFIG
            pg_config = PG_CONFIG
        self._cfg = pg_config

    def load_bar_data(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None,
    ) -> dict:
        import psycopg
        import pandas as pd

        code_filter = ""
        params: list = [start, end]
        if ts_codes:
            placeholders = ",".join(["%s"] * len(ts_codes))
            code_filter = f"AND ts_code IN ({placeholders})"
            params.extend(ts_codes)

        query = f"""
            SELECT
                trade_date::text AS trade_date,
                ts_code,
                close,
                vol AS volume,
                LAG(close) OVER (
                    PARTITION BY ts_code ORDER BY trade_date
                ) AS prev_close
            FROM daily_price
            WHERE trade_date BETWEEN %s AND %s {code_filter}
            ORDER BY trade_date, ts_code
        """
        conn = psycopg.connect(**self._cfg)
        df = pd.read_sql(query, conn, params=params)  # type: ignore[call-overload]
        conn.close()
        return self._df_to_dict(df)


# ── DuckDB 后端（CSV/Parquet）────────────────────────────────
class DuckDBDataFeed(BaseDataFeed):
    """DuckDB 数据源，优先年度 CSV，fallback 全量 Parquet（比 PG 快 100x）"""

    def __init__(
        self,
        csv_dir: str | None = None,
        parquet_path: str | None = None,
    ):
        self._csv_dir = Path(csv_dir) if csv_dir else _ROOT / "data" / "yearly"
        self._parquet = Path(parquet_path) if parquet_path else _ROOT / "data" / "daily_price_full.parquet"

    def load_bar_data(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None,
    ) -> dict:
        import duckdb
        con = duckdb.connect()
        sql = self._build_sql(start, end, ts_codes)
        df = con.execute(sql).fetchdf()
        con.close()
        return self._df_to_dict(df)

    def _build_sql(self, start: str, end: str, ts_codes: list[str] | None) -> str:
        start_year = int(start[:4])
        end_year   = int(end[:4])

        csv_files = [
            str(self._csv_dir / f"{yr}.csv")
            for yr in range(start_year, end_year + 1)
            if (self._csv_dir / f"{yr}.csv").exists()
        ]

        if csv_files:
            union = " UNION ALL ".join(
                f"SELECT * FROM read_csv_auto('{f}')" for f in csv_files
            )
            source = f"({union})"
        elif self._parquet.exists():
            source = f"'{self._parquet}'"
        else:
            raise FileNotFoundError(
                f"找不到数据: csv_dir={self._csv_dir}, parquet={self._parquet}"
            )

        code_filter = ""
        if ts_codes:
            codes_str = ", ".join(f"'{c}'" for c in ts_codes)
            code_filter = f"AND ts_code IN ({codes_str})"

        return f"""
            SELECT
                trade_date::VARCHAR AS trade_date,
                ts_code,
                close,
                volume,
                prev_close
            FROM {source}
            WHERE trade_date BETWEEN '{start}' AND '{end}'
              AND prev_close IS NOT NULL
              AND prev_close > 0
              {code_filter}
            ORDER BY trade_date, ts_code
        """


# ── SQLite 后端 ───────────────────────────────────────────────
class SQLiteDataFeed(BaseDataFeed):
    """SQLite 数据源（轻量，适合单机开发/测试）"""

    def __init__(self, db_path: str | None = None):
        self._db = Path(db_path) if db_path else _ROOT / "data" / "market.db"

    def load_bar_data(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None,
    ) -> dict:
        import sqlite3
        import pandas as pd

        conn = sqlite3.connect(self._db)
        params: list = [start, end]
        code_filter = ""
        if ts_codes:
            placeholders = ",".join(["?"] * len(ts_codes))
            code_filter = f"AND ts_code IN ({placeholders})"
            params.extend(ts_codes)

        query = f"""
            SELECT ts_code, trade_date, close, vol AS volume,
                   LAG(close) OVER (
                       PARTITION BY ts_code ORDER BY trade_date
                   ) AS prev_close
            FROM daily_price
            WHERE trade_date BETWEEN ? AND ? {code_filter}
            ORDER BY trade_date, ts_code
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return self._df_to_dict(df)


# ── 内存后端（测试用）────────────────────────────────────────
class MemoryDataFeed(BaseDataFeed):
    """内存数据源，直接传入 market_data dict，主要用于单元测试"""

    def __init__(self, market_data: dict):
        self._data = market_data

    def load_bar_data(
        self,
        start: str,
        end: str,
        ts_codes: list[str] | None = None,
    ) -> dict:
        result = {}
        for date, prices in self._data.items():
            if start <= date <= end:
                if ts_codes:
                    filtered = {k: v for k, v in prices.items() if k in ts_codes}
                    if filtered:
                        result[date] = filtered
                else:
                    result[date] = prices
        return result


# ── 工厂函数 ─────────────────────────────────────────────────
def create_datafeed(backend: str = "auto", **kwargs: Any) -> BaseDataFeed:
    """
    DataFeed 工厂

    backend: "auto" | "duckdb" | "postgres" | "sqlite" | "memory"

    示例:
        feed = create_datafeed()                           # 自动选择
        feed = create_datafeed("postgres")                 # 强制 PG
        feed = create_datafeed("memory", market_data={})   # 测试
    """
    if backend == "memory":
        return MemoryDataFeed(kwargs["market_data"])
    if backend == "postgres":
        return PostgresDataFeed(kwargs.get("pg_config"))
    if backend == "sqlite":
        return SQLiteDataFeed(kwargs.get("db_path"))
    if backend == "duckdb":
        return DuckDBDataFeed(
            csv_dir=kwargs.get("csv_dir"),
            parquet_path=kwargs.get("parquet_path"),
        )
    # auto: 优先 DuckDB，fallback PG
    csv_dir = _ROOT / "data" / "yearly"
    parquet  = _ROOT / "data" / "daily_price_full.parquet"
    if any(csv_dir.glob("*.csv")) or parquet.exists():
        return DuckDBDataFeed()
    return PostgresDataFeed()
