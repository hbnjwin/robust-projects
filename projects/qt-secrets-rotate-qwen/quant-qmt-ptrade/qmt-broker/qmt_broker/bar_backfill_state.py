import json
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence


class PostgresBarBackfillState:
    def __init__(
        self,
        dsn: str,
        schema: str = "public",
        coverage_table: str = "intraday_bar_coverage_1m",
        jobs_table: str = "intraday_bar_backfill_jobs",
    ) -> None:
        self._dsn = str(dsn or "").strip()
        self._schema = str(schema or "public").strip() or "public"
        self._coverage_table = str(coverage_table or "intraday_bar_coverage_1m").strip() or "intraday_bar_coverage_1m"
        self._jobs_table = str(jobs_table or "intraday_bar_backfill_jobs").strip() or "intraday_bar_backfill_jobs"

    def enabled(self) -> bool:
        return bool(self._dsn)

    def upsert_coverage(
        self,
        *,
        trade_date: date,
        symbol: str,
        period: str,
        stage: str,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        expected_bars: int,
        actual_bars: int,
        first_bar_time: Optional[datetime],
        last_bar_time: Optional[datetime],
        status: str,
        source: str,
        note: str = "",
        raw_json: Optional[Dict[str, object]] = None,
    ) -> None:
        if not self.enabled():
            return
        try:
            import psycopg
            from psycopg import sql
            from psycopg.types.json import Jsonb
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        completeness_ratio = 0.0
        if expected_bars > 0:
            completeness_ratio = min(float(actual_bars) / float(expected_bars), 1.0)
        query = sql.SQL(
            """
            INSERT INTO {}.{} (
              trade_date,
              ts_code,
              period,
              stage,
              window_start_time,
              window_end_time,
              expected_bars,
              actual_bars,
              completeness_ratio,
              first_bar_time,
              last_bar_time,
              status,
              source,
              note,
              raw_json
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (trade_date, ts_code, period, stage) DO UPDATE
            SET
              window_start_time = EXCLUDED.window_start_time,
              window_end_time = EXCLUDED.window_end_time,
              expected_bars = EXCLUDED.expected_bars,
              actual_bars = EXCLUDED.actual_bars,
              completeness_ratio = EXCLUDED.completeness_ratio,
              first_bar_time = EXCLUDED.first_bar_time,
              last_bar_time = EXCLUDED.last_bar_time,
              status = EXCLUDED.status,
              source = EXCLUDED.source,
              note = EXCLUDED.note,
              raw_json = EXCLUDED.raw_json,
              updated_at = NOW()
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._coverage_table))
        payload = raw_json if isinstance(raw_json, dict) else {}
        params = (
            trade_date,
            str(symbol or "").strip().upper(),
            str(period or "1m").strip().lower() or "1m",
            str(stage or "").strip().lower(),
            window_start,
            window_end,
            max(int(expected_bars), 0),
            max(int(actual_bars), 0),
            completeness_ratio,
            first_bar_time,
            last_bar_time,
            str(status or "").strip().lower(),
            str(source or "").strip(),
            str(note or ""),
            Jsonb(_json_ready(payload)),
        )
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()

    def upsert_job(
        self,
        *,
        job_key: str,
        trade_date: date,
        symbol: str,
        period: str,
        stage: str,
        scheduler_source: str,
        status: str,
        attempt_count: int,
        expected_bars: int,
        actual_bars: int,
        written_rows: int,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        started_at: Optional[datetime],
        finished_at: Optional[datetime],
        last_error: str = "",
        detail: str = "",
        raw_json: Optional[Dict[str, object]] = None,
    ) -> None:
        if not self.enabled():
            return
        try:
            import psycopg
            from psycopg import sql
            from psycopg.types.json import Jsonb
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            INSERT INTO {}.{} (
              job_key,
              trade_date,
              ts_code,
              period,
              stage,
              scheduler_source,
              status,
              attempt_count,
              expected_bars,
              actual_bars,
              written_rows,
              window_start_time,
              window_end_time,
              started_at,
              finished_at,
              last_error,
              detail,
              raw_json
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (job_key) DO UPDATE
            SET
              status = EXCLUDED.status,
              attempt_count = EXCLUDED.attempt_count,
              expected_bars = EXCLUDED.expected_bars,
              actual_bars = EXCLUDED.actual_bars,
              written_rows = EXCLUDED.written_rows,
              window_start_time = EXCLUDED.window_start_time,
              window_end_time = EXCLUDED.window_end_time,
              started_at = COALESCE(EXCLUDED.started_at, {}.{}.started_at),
              finished_at = EXCLUDED.finished_at,
              last_error = EXCLUDED.last_error,
              detail = EXCLUDED.detail,
              raw_json = EXCLUDED.raw_json,
              updated_at = NOW()
            """
        ).format(
            sql.Identifier(self._schema),
            sql.Identifier(self._jobs_table),
            sql.Identifier(self._schema),
            sql.Identifier(self._jobs_table),
        )
        payload = raw_json if isinstance(raw_json, dict) else {}
        params = (
            str(job_key or "").strip(),
            trade_date,
            str(symbol or "").strip().upper(),
            str(period or "1m").strip().lower() or "1m",
            str(stage or "").strip().lower(),
            str(scheduler_source or "serve").strip().lower(),
            str(status or "").strip().lower(),
            max(int(attempt_count), 0),
            max(int(expected_bars), 0),
            max(int(actual_bars), 0),
            max(int(written_rows), 0),
            window_start,
            window_end,
            started_at,
            finished_at,
            str(last_error or ""),
            str(detail or ""),
            Jsonb(_json_ready(payload)),
        )
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
            conn.commit()

    def load_coverage_rows(
        self,
        *,
        symbols: Sequence[str],
        trade_date_from: date,
        trade_date_to: date,
        period: str = "1m",
        stages: Sequence[str] = (),
    ) -> List[Dict[str, object]]:
        clean_symbols = [str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()]
        clean_stages = [str(stage or "").strip().lower() for stage in stages if str(stage or "").strip()]
        if not self.enabled() or not clean_symbols:
            return []
        try:
            import psycopg
            from psycopg import sql
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            SELECT
              trade_date,
              ts_code,
              period,
              stage,
              window_start_time,
              window_end_time,
              expected_bars,
              actual_bars,
              completeness_ratio,
              first_bar_time,
              last_bar_time,
              status,
              source,
              note,
              raw_json,
              updated_at
            FROM {}.{}
            WHERE trade_date BETWEEN %s AND %s
              AND period = %s
              AND ts_code = ANY(%s)
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._coverage_table))
        params: List[object] = [
            trade_date_from,
            trade_date_to,
            str(period or "1m").strip().lower() or "1m",
            clean_symbols,
        ]
        if clean_stages:
            query += sql.SQL(" AND stage = ANY(%s)")
            params.append(clean_stages)
        query += sql.SQL(" ORDER BY trade_date DESC, ts_code ASC, updated_at DESC")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        results: List[Dict[str, object]] = []
        for row in rows:
            results.append(
                {
                    "trade_date": row[0],
                    "ts_code": row[1],
                    "period": row[2],
                    "stage": row[3],
                    "window_start_time": row[4],
                    "window_end_time": row[5],
                    "expected_bars": int(row[6] or 0),
                    "actual_bars": int(row[7] or 0),
                    "completeness_ratio": float(row[8] or 0.0),
                    "first_bar_time": row[9],
                    "last_bar_time": row[10],
                    "status": row[11],
                    "source": row[12],
                    "note": row[13],
                    "raw_json": row[14] if isinstance(row[14], dict) else {},
                    "updated_at": row[15],
                }
            )
        return results


def _json_ready(payload: Dict[str, object]) -> Dict[str, object]:
    encoded = json.loads(json.dumps(payload, ensure_ascii=False, default=_json_default))
    return encoded if isinstance(encoded, dict) else {}


def _json_default(value: object):  # type: ignore[no-untyped-def]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return str(value)
