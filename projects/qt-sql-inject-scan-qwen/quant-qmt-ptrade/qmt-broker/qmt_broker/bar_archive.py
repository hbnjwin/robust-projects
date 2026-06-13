import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional


CN_TZ = timezone(timedelta(hours=8))


class PostgresBarArchive:
    def __init__(self, dsn: str, schema: str = "public", table: str = "intraday_bars_1m") -> None:
        self._dsn = str(dsn or "").strip()
        self._schema = str(schema or "public").strip() or "public"
        self._table = str(table or "intraday_bars_1m").strip() or "intraday_bars_1m"

    def enabled(self) -> bool:
        return bool(self._dsn)

    def upsert_bars(
        self,
        symbol: str,
        period: str,
        rows: Iterable[Dict[str, object]],
        *,
        source: str = "xtquant",
    ) -> int:
        clean_symbol = str(symbol or "").strip().upper()
        clean_period = str(period or "1m").strip().lower() or "1m"
        if not clean_symbol:
            return 0
        if not self.enabled():
            raise RuntimeError("bar archive is disabled")
        normalized_rows = [self._build_row(clean_symbol, clean_period, row, source) for row in rows]
        normalized_rows = [row for row in normalized_rows if row is not None]
        if not normalized_rows:
            return 0
        try:
            import psycopg
            from psycopg import sql
            from psycopg.types.json import Jsonb
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            INSERT INTO {}.{} (
              trade_date,
              ts_code,
              period,
              bar_time,
              open_price,
              high_price,
              low_price,
              close_price,
              volume,
              amount,
              source,
              raw_json
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (trade_date, ts_code, period, bar_time) DO UPDATE
            SET
              open_price = EXCLUDED.open_price,
              high_price = EXCLUDED.high_price,
              low_price = EXCLUDED.low_price,
              close_price = EXCLUDED.close_price,
              volume = EXCLUDED.volume,
              amount = EXCLUDED.amount,
              source = EXCLUDED.source,
              raw_json = EXCLUDED.raw_json,
              updated_at = NOW()
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table))
        params = [
            (
                row["trade_date"],
                row["ts_code"],
                row["period"],
                row["bar_time"],
                row["open_price"],
                row["high_price"],
                row["low_price"],
                row["close_price"],
                row["volume"],
                row["amount"],
                row["source"],
                Jsonb(row["raw_json"]),
            )
            for row in normalized_rows
        ]
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params)
            conn.commit()
        return len(normalized_rows)

    def count_bars(
        self,
        symbol: str,
        trade_date_text: str,
        period: str = "1m",
    ) -> int:
        clean_symbol = str(symbol or "").strip().upper()
        clean_period = str(period or "1m").strip().lower() or "1m"
        clean_trade_date = str(trade_date_text or "").strip()
        if not clean_symbol or not clean_trade_date:
            return 0
        if not self.enabled():
            raise RuntimeError("bar archive is disabled")
        try:
            import psycopg
            from psycopg import sql
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            SELECT COUNT(*)
            FROM {}.{}
            WHERE trade_date = %s
              AND ts_code = %s
              AND period = %s
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (clean_trade_date, clean_symbol, clean_period))
                row = cur.fetchone()
        return int(row[0]) if row else 0

    def describe_bars(
        self,
        symbol: str,
        trade_date_text: str,
        period: str = "1m",
    ) -> Dict[str, object]:
        clean_symbol = str(symbol or "").strip().upper()
        clean_period = str(period or "1m").strip().lower() or "1m"
        clean_trade_date = str(trade_date_text or "").strip()
        if not clean_symbol or not clean_trade_date:
            return {"count": 0, "first_bar_time": None, "last_bar_time": None}
        if not self.enabled():
            raise RuntimeError("bar archive is disabled")
        try:
            import psycopg
            from psycopg import sql
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            SELECT COUNT(*) AS count, MIN(bar_time) AS first_bar_time, MAX(bar_time) AS last_bar_time
            FROM {}.{}
            WHERE trade_date = %s
              AND ts_code = %s
              AND period = %s
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (clean_trade_date, clean_symbol, clean_period))
                row = cur.fetchone()
        return {
            "count": int(row[0]) if row else 0,
            "first_bar_time": row[1] if row else None,
            "last_bar_time": row[2] if row else None,
        }

    def describe_bars_window(
        self,
        symbol: str,
        period: str = "1m",
        *,
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> Dict[str, object]:
        clean_symbol = str(symbol or "").strip().upper()
        clean_period = str(period or "1m").strip().lower() or "1m"
        if not clean_symbol or window_start is None or window_end is None:
            return {"count": 0, "first_bar_time": None, "last_bar_time": None}
        if not self.enabled():
            raise RuntimeError("bar archive is disabled")
        try:
            import psycopg
            from psycopg import sql
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            SELECT COUNT(*) AS count, MIN(bar_time) AS first_bar_time, MAX(bar_time) AS last_bar_time
            FROM {}.{}
            WHERE ts_code = %s
              AND period = %s
              AND bar_time >= %s
              AND bar_time < %s
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table))
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (clean_symbol, clean_period, window_start, window_end))
                row = cur.fetchone()
        return {
            "count": int(row[0]) if row else 0,
            "first_bar_time": row[1] if row else None,
            "last_bar_time": row[2] if row else None,
        }

    def _build_row(
        self,
        symbol: str,
        period: str,
        row: Dict[str, object],
        source: str,
    ) -> Optional[Dict[str, object]]:
        bar_time = self._parse_bar_time(row.get("time"))
        if bar_time is None:
            return None
        return {
            "trade_date": bar_time.date(),
            "ts_code": symbol,
            "period": period,
            "bar_time": bar_time,
            "open_price": row.get("open"),
            "high_price": row.get("high"),
            "low_price": row.get("low"),
            "close_price": row.get("close"),
            "volume": self._int_value(row.get("volume")),
            "amount": self._float_value(row.get("amount")),
            "source": str(source or "xtquant"),
            "raw_json": self._json_ready(row),
        }

    def _parse_bar_time(self, value: object) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=CN_TZ)
        text = str(value).strip()
        if not text:
            return None
        if text.isdigit():
            if len(text) == 14:
                return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=CN_TZ)
            if len(text) >= 10:
                return datetime.fromtimestamp(int(text) / 1000.0, tz=CN_TZ)
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=CN_TZ)

    def _json_ready(self, row: Dict[str, object]) -> Dict[str, object]:
        encoded = json.loads(json.dumps(row, ensure_ascii=False, default=self._json_default))
        return encoded if isinstance(encoded, dict) else {}

    def _json_default(self, value: object):  # type: ignore[no-untyped-def]
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return str(value)
        return str(value)

    def _int_value(self, value: object) -> int:
        try:
            return int(value or 0)
        except Exception:
            return 0

    def _float_value(self, value: object) -> float:
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0
