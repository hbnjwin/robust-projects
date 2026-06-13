import queue
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional


CN_TZ = timezone(timedelta(hours=8))


class PostgresTickArchive:
    def __init__(
        self,
        dsn: str,
        schema: str = "public",
        table: str = "intraday_ticks",
        batch_size: int = 200,
        flush_interval_sec: int = 1,
        queue_size: int = 50000,
        reconnect_retry_sec: int = 5,
    ) -> None:
        self._dsn = str(dsn or "").strip()
        self._schema = str(schema or "public").strip() or "public"
        self._table = str(table or "intraday_ticks").strip() or "intraday_ticks"
        self._batch_size = max(1, int(batch_size))
        self._flush_interval_sec = max(1, int(flush_interval_sec))
        self._queue_size = max(1, int(queue_size))
        self._reconnect_retry_sec = max(1, int(reconnect_retry_sec))
        self._queue: "queue.Queue[Dict[str, object]]" = queue.Queue(self._queue_size)
        self._lock = threading.RLock()
        self._running = bool(self._dsn)
        self._thread: Optional[threading.Thread] = None
        self._conn = None
        self._last_error = ""
        self._next_retry_at = 0.0
        self._pending_count = 0
        self._dropped_count = 0
        self._written_count = 0
        self._last_ping_ms = 0
        if self.enabled():
            self._thread = threading.Thread(target=self._worker_loop, daemon=True)
            self._thread.start()

    def enabled(self) -> bool:
        return bool(self._dsn)

    def append_event(self, symbol: str, event: Dict[str, object]) -> None:
        if not self.enabled():
            return
        row = self._build_row(symbol, event)
        if row is None:
            return
        try:
            self._queue.put_nowait(row)
        except queue.Full:
            with self._lock:
                self._dropped_count += 1
                self._last_error = "tick_archive_queue_full"
            return
        with self._lock:
            self._pending_count += 1

    def status(self) -> Dict[str, object]:
        with self._lock:
            return {
                "enabled": self.enabled(),
                "backend": "postgres" if self.enabled() else "disabled",
                "connected": self._conn is not None,
                "schema": self._schema,
                "table": self._table,
                "pending_count": self._pending_count,
                "dropped_count": self._dropped_count,
                "written_count": self._written_count,
                "last_error": self._last_error,
                "last_ping_ms": self._last_ping_ms,
                "batch_size": self._batch_size,
                "flush_interval_sec": self._flush_interval_sec,
            }

    def ping(self) -> bool:
        if not self.enabled():
            return False
        conn = self._ensure_conn(force=True)
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except Exception as exc:
            self._drop_conn(str(exc), conn)
            return False
        with self._lock:
            self._last_error = ""
            self._last_ping_ms = int(time.time() * 1000)
        return True

    def query_ticks(
        self,
        symbol: str,
        trade_date_text: str = "",
        limit: int = 500,
    ) -> List[Dict[str, object]]:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return []
        if not self.enabled():
            raise RuntimeError("tick archive is disabled")
        query_trade_date = self._parse_trade_date(trade_date_text)
        conn = self._ensure_conn(force=True)
        if conn is None:
            raise RuntimeError(self._last_error or "tick archive is unavailable")
        try:
            from psycopg import rows, sql
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise RuntimeError(str(exc)) from exc
        try:
            rows_out = self._query_rows(conn, clean_symbol, query_trade_date, max(1, int(limit)), rows, sql)
        except Exception as exc:
            self._drop_conn(str(exc), conn)
            raise RuntimeError(str(exc)) from exc
        with self._lock:
            self._last_error = ""
            self._last_ping_ms = int(time.time() * 1000)
        rows_out.reverse()
        return [dict(row) for row in rows_out]

    def count_ticks(
        self,
        symbol: str,
        trade_date_text: str = "",
    ) -> int:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return 0
        if not self.enabled():
            raise RuntimeError("tick archive is disabled")
        query_trade_date = self._parse_trade_date(trade_date_text)
        conn = self._ensure_conn(force=True)
        if conn is None:
            raise RuntimeError(self._last_error or "tick archive is unavailable")
        try:
            from psycopg import sql
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL("SELECT COUNT(*) FROM {}.{} WHERE ts_code = %s AND trade_date = %s").format(
            sql.Identifier(self._schema),
            sql.Identifier(self._table),
        )
        try:
            with conn.cursor() as cur:
                cur.execute(query, [clean_symbol, query_trade_date])
                row = cur.fetchone()
        except Exception as exc:
            self._drop_conn(str(exc), conn)
            raise RuntimeError(str(exc)) from exc
        with self._lock:
            self._last_error = ""
            self._last_ping_ms = int(time.time() * 1000)
        return int(row[0]) if row else 0

    def query_bars(
        self,
        symbol: str,
        trade_date_text: str = "",
        period: str = "1m",
        limit: int = 240,
    ) -> List[Dict[str, object]]:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return []
        if not self.enabled():
            raise RuntimeError("tick archive is disabled")
        bucket_minutes = self._period_to_minutes(period)
        query_trade_date = self._parse_trade_date(trade_date_text)
        conn = self._ensure_conn(force=True)
        if conn is None:
            raise RuntimeError(self._last_error or "tick archive is unavailable")
        try:
            from psycopg import rows, sql
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise RuntimeError(str(exc)) from exc
        try:
            rows_out = self._query_rows(conn, clean_symbol, query_trade_date, None, rows, sql)
        except Exception as exc:
            self._drop_conn(str(exc), conn)
            raise RuntimeError(str(exc)) from exc
        with self._lock:
            self._last_error = ""
            self._last_ping_ms = int(time.time() * 1000)
        return self._aggregate_rows_to_bars([dict(row) for row in rows_out], bucket_minutes, max(1, int(limit)))

    def query_feature_summary(
        self,
        symbol: str,
        trade_date_text: str = "",
    ) -> Dict[str, object]:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return {}
        if not self.enabled():
            raise RuntimeError("tick archive is disabled")
        query_trade_date = self._parse_trade_date(trade_date_text)
        conn = self._ensure_conn(force=True)
        if conn is None:
            raise RuntimeError(self._last_error or "tick archive is unavailable")
        try:
            from psycopg import rows, sql
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            raise RuntimeError(str(exc)) from exc
        try:
            rows_out = self._query_rows(conn, clean_symbol, query_trade_date, None, rows, sql)
        except Exception as exc:
            self._drop_conn(str(exc), conn)
            raise RuntimeError(str(exc)) from exc
        with self._lock:
            self._last_error = ""
            self._last_ping_ms = int(time.time() * 1000)
        return self._build_feature_summary([dict(row) for row in rows_out], clean_symbol, query_trade_date.isoformat())

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        with self._lock:
            conn = self._conn
            self._conn = None
        if conn is None:
            return
        try:
            conn.close()
        except Exception:
            return

    def _worker_loop(self) -> None:
        batch: List[Dict[str, object]] = []
        while self._running or not self._queue.empty() or batch:
            try:
                row = self._queue.get(timeout=self._flush_interval_sec)
                batch.append(row)
            except queue.Empty:
                if batch and self._flush_batch(batch):
                    batch = []
                continue
            while len(batch) < self._batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if batch and self._flush_batch(batch):
                batch = []

    def _flush_batch(self, batch: List[Dict[str, object]]) -> bool:
        if not batch:
            return True
        conn = self._ensure_conn()
        if conn is None:
            time.sleep(self._reconnect_retry_sec)
            return False
        try:
            import psycopg
            from psycopg import sql
            from psycopg.types.json import Jsonb
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
            time.sleep(self._reconnect_retry_sec)
            return False
        query = sql.SQL(
            """
            INSERT INTO {}.{} (
              trade_date,
              ts_code,
              tick_time,
              tick_time_ms,
              last_price,
              open_price,
              high_price,
              low_price,
              last_close,
              amount,
              volume,
              pvolume,
              tickvol,
              stock_status,
              open_int,
              settlement_price,
              last_settlement_price,
              transaction_num,
              ask_price,
              bid_price,
              ask_vol,
              bid_vol,
              source
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (trade_date, ts_code, tick_time_ms) DO NOTHING
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table))
        rows = [
            (
                row["trade_date"],
                row["ts_code"],
                row["tick_time"],
                row["tick_time_ms"],
                row["last_price"],
                row["open_price"],
                row["high_price"],
                row["low_price"],
                row["last_close"],
                row["amount"],
                row["volume"],
                row["pvolume"],
                row["tickvol"],
                row["stock_status"],
                row["open_int"],
                row["settlement_price"],
                row["last_settlement_price"],
                row["transaction_num"],
                Jsonb(row["ask_price"]),
                Jsonb(row["bid_price"]),
                Jsonb(row["ask_vol"]),
                Jsonb(row["bid_vol"]),
                row["source"],
            )
            for row in batch
        ]
        try:
            with conn.cursor() as cur:
                cur.executemany(query, rows)
            conn.commit()
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            with self._lock:
                self._conn = None
                self._last_error = str(exc)
                self._next_retry_at = time.time() + self._reconnect_retry_sec
            try:
                conn.close()
            except Exception:
                pass
            time.sleep(self._reconnect_retry_sec)
            return False
        with self._lock:
            self._last_error = ""
            self._pending_count = max(0, self._pending_count - len(batch))
            self._written_count += len(batch)
        return True

    def _ensure_conn(self, force: bool = False):
        if not self.enabled():
            return None
        with self._lock:
            if self._conn is not None:
                return self._conn
            if not force and time.time() < self._next_retry_at:
                return None
        try:
            import psycopg

            conn = psycopg.connect(self._dsn)
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
                self._next_retry_at = time.time() + self._reconnect_retry_sec
            return None
        with self._lock:
            self._conn = conn
            self._last_error = ""
            self._next_retry_at = 0.0
            return self._conn

    def _query_rows(self, conn, symbol: str, trade_date_value: date, limit: Optional[int], rows, sql):  # type: ignore[no-untyped-def]
        limit_sql = sql.SQL("LIMIT %s") if limit is not None else sql.SQL("")
        query = sql.SQL(
            """
            SELECT
              trade_date,
              ts_code,
              tick_time,
              tick_time_ms,
              last_price,
              open_price,
              high_price,
              low_price,
              last_close,
              amount,
              volume,
              pvolume,
              tickvol,
              stock_status,
              open_int,
              settlement_price,
              last_settlement_price,
              transaction_num,
              ask_price,
              bid_price,
              ask_vol,
              bid_vol,
              source,
              created_at
            FROM {}.{}
            WHERE ts_code = %s AND trade_date = %s
            ORDER BY tick_time_ms DESC
            {}
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table), limit_sql)
        params = [symbol, trade_date_value]
        if limit is not None:
            params.append(limit)
        with conn.cursor(row_factory=rows.dict_row) as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def _drop_conn(self, error_text: str, conn) -> None:  # type: ignore[no-untyped-def]
        try:
            conn.rollback()
        except Exception:
            pass
        with self._lock:
            self._conn = None
            self._last_error = error_text
            self._next_retry_at = time.time() + self._reconnect_retry_sec
        try:
            conn.close()
        except Exception:
            pass

    def _parse_trade_date(self, trade_date_text: str) -> date:
        clean = str(trade_date_text or "").strip()
        if not clean:
            return datetime.now(tz=CN_TZ).date()
        try:
            return date.fromisoformat(clean)
        except ValueError as exc:
            raise RuntimeError("invalid trade_date, expected YYYY-MM-DD") from exc

    def _period_to_minutes(self, period: str) -> int:
        clean = str(period or "1m").strip().lower()
        if clean == "1m":
            return 1
        if clean == "5m":
            return 5
        if clean == "15m":
            return 15
        raise RuntimeError("unsupported period, expected 1m, 5m or 15m")

    def _aggregate_rows_to_bars(
        self,
        rows: List[Dict[str, object]],
        bucket_minutes: int,
        limit: int,
    ) -> List[Dict[str, object]]:
        if not rows:
            return []
        ordered = sorted(rows, key=lambda row: self._int_value(row.get("tick_time_ms")))
        bars: List[Dict[str, object]] = []
        current_bar: Optional[Dict[str, object]] = None
        current_bucket_ms = -1
        prev_volume = 0.0
        prev_amount = 0.0
        has_prev_volume = False
        has_prev_amount = False
        bucket_ms = bucket_minutes * 60 * 1000
        for row in ordered:
            tick_ms = self._int_value(row.get("tick_time_ms"))
            last_price = self._float_value(row.get("last_price"))
            if tick_ms <= 0 or last_price <= 0:
                continue
            volume = self._float_value(row.get("volume"))
            amount = self._float_value(row.get("amount"))
            delta_volume = volume - prev_volume if has_prev_volume else volume
            delta_amount = amount - prev_amount if has_prev_amount else amount
            prev_volume = volume
            prev_amount = amount
            has_prev_volume = True
            has_prev_amount = True
            if delta_volume < 0:
                delta_volume = 0.0
            if delta_amount < 0:
                delta_amount = 0.0
            tick_dt = datetime.fromtimestamp(tick_ms / 1000.0, tz=CN_TZ)
            bucket_dt = tick_dt.replace(
                minute=(tick_dt.minute // bucket_minutes) * bucket_minutes,
                second=0,
                microsecond=0,
            )
            bucket_key = int(bucket_dt.timestamp() * 1000)
            if bucket_key != current_bucket_ms:
                current_bar = {
                    "time": bucket_dt.strftime("%Y%m%d%H%M%S"),
                    "open": last_price,
                    "high": last_price,
                    "low": last_price,
                    "close": last_price,
                    "volume": int(round(delta_volume)),
                    "amount": delta_amount,
                    "tick_count": 1,
                }
                bars.append(current_bar)
                current_bucket_ms = bucket_key
                continue
            assert current_bar is not None
            current_bar["high"] = max(self._float_value(current_bar.get("high")), last_price)
            current_bar["low"] = min(self._float_value(current_bar.get("low")), last_price)
            current_bar["close"] = last_price
            current_bar["volume"] = int(round(self._float_value(current_bar.get("volume")) + delta_volume))
            current_bar["amount"] = self._float_value(current_bar.get("amount")) + delta_amount
            current_bar["tick_count"] = int(current_bar.get("tick_count", 0)) + 1
        return bars[-limit:]

    def _build_feature_summary(
        self,
        rows: List[Dict[str, object]],
        symbol: str,
        trade_date_text: str,
    ) -> Dict[str, object]:
        ordered = sorted(rows, key=lambda row: self._int_value(row.get("tick_time_ms")))
        valid_rows = []
        for row in ordered:
            tick_time_ms = self._int_value(row.get("tick_time_ms"))
            last_price = self._float_value(row.get("last_price"))
            if tick_time_ms <= 0 or last_price <= 0:
                continue
            valid_rows.append(
                {
                    "tick_time_ms": tick_time_ms,
                    "last_price": last_price,
                    "volume": self._float_value(row.get("volume")),
                    "amount": self._float_value(row.get("amount")),
                }
            )

        summary: Dict[str, object] = {
            "symbol": symbol,
            "trade_date": trade_date_text,
            "tick_count": len(valid_rows),
            "bar_count_1m": 0,
            "bar_count_5m": 0,
            "bar_count_15m": 0,
        }
        if not valid_rows:
            return summary

        open_price = valid_rows[0]["last_price"]
        close_price = valid_rows[-1]["last_price"]
        high_price = max(row["last_price"] for row in valid_rows)
        low_price = min(row["last_price"] for row in valid_rows)
        volume_total = max(0.0, valid_rows[-1]["volume"])
        amount_total = max(0.0, valid_rows[-1]["amount"])
        vwap = amount_total / volume_total if volume_total > 0 else 0.0

        morning_rows = [
            row
            for row in valid_rows
            if self._in_session_window(self._int_value(row["tick_time_ms"]), start_hour=9, start_minute=30, end_hour=11, end_minute=30)
        ]
        afternoon_rows = [
            row
            for row in valid_rows
            if self._in_session_window(self._int_value(row["tick_time_ms"]), start_hour=13, start_minute=0, end_hour=15, end_minute=0)
        ]

        bars_1m = self._aggregate_rows_to_bars(rows, 1, 10_000)
        bars_5m = self._aggregate_rows_to_bars(rows, 5, 10_000)
        bars_15m = self._aggregate_rows_to_bars(rows, 15, 10_000)

        summary.update(
            {
                "first_tick_time_ms": self._int_value(valid_rows[0]["tick_time_ms"]),
                "last_tick_time_ms": self._int_value(valid_rows[-1]["tick_time_ms"]),
                "open": open_price,
                "close": close_price,
                "high": high_price,
                "low": low_price,
                "day_return_pct": self._pct_change(close_price, open_price),
                "amplitude_pct": ((high_price - low_price) / open_price * 100.0) if open_price > 0 else 0.0,
                "volume_total": int(round(volume_total)),
                "amount_total": amount_total,
                "vwap": vwap,
                "close_vs_vwap_pct": self._pct_change(close_price, vwap),
                "bar_count_1m": len(bars_1m),
                "bar_count_5m": len(bars_5m),
                "bar_count_15m": len(bars_15m),
                "morning_return_pct": self._session_return(morning_rows),
                "afternoon_return_pct": self._session_return(afternoon_rows),
            }
        )
        return summary

    def _in_session_window(
        self,
        tick_time_ms: int,
        *,
        start_hour: int,
        start_minute: int,
        end_hour: int,
        end_minute: int,
    ) -> bool:
        tick_dt = datetime.fromtimestamp(tick_time_ms / 1000.0, tz=CN_TZ)
        session_start = tick_dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        session_end = tick_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        return session_start <= tick_dt < session_end

    def _pct_change(self, current: float, baseline: float) -> float:
        if baseline <= 0:
            return 0.0
        return (current - baseline) / baseline * 100.0

    def _session_return(self, rows: List[Dict[str, float]]) -> float:
        if len(rows) < 2:
            return 0.0
        return self._pct_change(rows[-1]["last_price"], rows[0]["last_price"])

    def _build_row(self, symbol: str, event: Dict[str, object]) -> Optional[Dict[str, object]]:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            return None
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return None
        tick_time_ms = self._int_value(payload.get("time"))
        if tick_time_ms <= 0:
            return None
        tick_dt = datetime.fromtimestamp(tick_time_ms / 1000.0, tz=CN_TZ)
        return {
            "trade_date": tick_dt.date(),
            "ts_code": clean_symbol,
            "tick_time": tick_dt,
            "tick_time_ms": tick_time_ms,
            "last_price": payload.get("lastPrice"),
            "open_price": payload.get("open"),
            "high_price": payload.get("high"),
            "low_price": payload.get("low"),
            "last_close": payload.get("lastClose"),
            "amount": payload.get("amount"),
            "volume": payload.get("volume"),
            "pvolume": payload.get("pvolume"),
            "tickvol": payload.get("tickvol"),
            "stock_status": payload.get("stockStatus"),
            "open_int": payload.get("openInt"),
            "settlement_price": payload.get("settlementPrice"),
            "last_settlement_price": payload.get("lastSettlementPrice"),
            "transaction_num": payload.get("transactionNum"),
            "ask_price": self._json_array(payload.get("askPrice")),
            "bid_price": self._json_array(payload.get("bidPrice")),
            "ask_vol": self._json_array(payload.get("askVol")),
            "bid_vol": self._json_array(payload.get("bidVol")),
            "source": str(event.get("provider") or "xtquant"),
        }

    def _json_array(self, value: object) -> List[object]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return []

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
