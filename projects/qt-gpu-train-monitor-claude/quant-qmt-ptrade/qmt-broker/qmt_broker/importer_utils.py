from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CN_TZ = timezone(timedelta(hours=8))


def ensure_xtquant_importable(project_root: Path) -> None:
    try:
        __import__("xtquant")
        return
    except Exception:
        pass
    xtquant_root = project_root / "XtQuant"
    if xtquant_root.is_dir():
        sys.path.insert(0, str(xtquant_root))


def normalize_scalar(value: Any) -> Any:
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def json_ready(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def normalize_records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        try:
            records = frame.to_dict(orient="records")
        except TypeError:
            records = frame.to_dict("records")
        if not isinstance(records, list):
            return []
        index_values = list(frame.index) if hasattr(frame, "index") else []
        normalized_records: list[dict[str, Any]] = []
        for idx, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            normalized = {str(key): normalize_scalar(value) for key, value in record.items()}
            if idx < len(index_values):
                normalized.setdefault("time", normalize_scalar(index_values[idx]))
            normalized_records.append(normalized)
        return normalized_records
    if hasattr(frame, "dtype") and getattr(frame.dtype, "names", None):
        names = list(frame.dtype.names)
        return [{name: normalize_scalar(row[name]) for name in names} for row in frame]
    if isinstance(frame, list):
        normalized_records = []
        for item in frame:
            if isinstance(item, Mapping):
                normalized_records.append({str(key): normalize_scalar(value) for key, value in item.items()})
        return normalized_records
    return []


def clean_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def split_symbol(symbol: str) -> tuple[str, str]:
    clean = clean_symbol(symbol)
    if "." not in clean:
        return clean, ""
    code, exchange = clean.split(".", 1)
    return code, exchange


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, float):
        return math.isnan(value)
    return False


def first_present(record: Mapping[str, Any], candidates: Sequence[str]) -> Any:
    lowered = {str(key).lower(): value for key, value in record.items()}
    for candidate in candidates:
        if candidate in record and not is_missing(record[candidate]):
            return normalize_scalar(record[candidate])
        lowered_candidate = str(candidate).lower()
        if lowered_candidate in lowered and not is_missing(lowered[lowered_candidate]):
            return normalize_scalar(lowered[lowered_candidate])
    return None


def parse_cn_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=CN_TZ)
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        if len(text) == 13:
            return datetime.fromtimestamp(int(text) / 1000.0, tz=CN_TZ)
        if len(text) == 10:
            return datetime.fromtimestamp(int(text), tz=CN_TZ)
        if len(text) == 14:
            return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=CN_TZ)
        if len(text) == 12:
            return datetime.strptime(text, "%Y%m%d%H%M").replace(tzinfo=CN_TZ)
        if len(text) == 8:
            return datetime.strptime(text, "%Y%m%d").replace(tzinfo=CN_TZ)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=CN_TZ)
        except ValueError:
            continue
    return None


def parse_cn_date(value: Any) -> date | None:
    parsed = parse_cn_datetime(value)
    return parsed.date() if parsed is not None else None


class DynamicPostgresUpsertStore:
    def __init__(self, dsn: str, schema: str = "public", table: str = "") -> None:
        self._dsn = str(dsn or "").strip()
        self._schema = str(schema or "public").strip() or "public"
        self._table = str(table or "").strip()

    def enabled(self) -> bool:
        return bool(self._dsn and self._table)

    def upsert_rows(self, rows: Iterable[dict[str, Any]]) -> int:
        prepared_rows = [row for row in rows if isinstance(row, dict) and row]
        if not prepared_rows:
            return 0
        if not self.enabled():
            raise RuntimeError("postgres store is disabled")
        try:
            import psycopg
            from psycopg import sql
            from psycopg.types.json import Jsonb
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, udt_name
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (self._schema, self._table),
                )
                column_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                    WHERE tc.table_schema = %s
                      AND tc.table_name = %s
                      AND tc.constraint_type = 'PRIMARY KEY'
                    ORDER BY kcu.ordinal_position
                    """,
                    (self._schema, self._table),
                )
                primary_key_rows = cur.fetchall()
            conn.commit()
        if not column_rows:
            raise RuntimeError(f"table {self._schema}.{self._table} does not exist or has no visible columns")
        column_types = {str(name): str(udt_name) for name, udt_name in column_rows}
        ordered_columns = [str(name) for name, _ in column_rows]
        primary_keys = [str(row[0]) for row in primary_key_rows]
        insert_columns = [column for column in ordered_columns if any(column in row for row in prepared_rows)]
        if not insert_columns:
            raise RuntimeError(
                f"no matching columns found for {self._schema}.{self._table}; sample keys: {sorted(prepared_rows[0].keys())}"
            )
        params = []
        for row in prepared_rows:
            values = []
            for column in insert_columns:
                value = row.get(column)
                if value is not None and column_types.get(column) in {"json", "jsonb"}:
                    value = Jsonb(json_ready(value))
                values.append(value)
            params.append(tuple(values))
        identifiers = sql.SQL(", ").join(sql.Identifier(column) for column in insert_columns)
        placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in insert_columns)
        query = sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
            sql.Identifier(self._schema),
            sql.Identifier(self._table),
            identifiers,
            placeholders,
        )
        if primary_keys and all(column in insert_columns for column in primary_keys):
            update_columns = [column for column in insert_columns if column not in primary_keys]
            if update_columns:
                query += sql.SQL(" ON CONFLICT ({}) DO UPDATE SET {}").format(
                    sql.SQL(", ").join(sql.Identifier(column) for column in primary_keys),
                    sql.SQL(", ").join(
                        sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
                        for column in update_columns
                    ),
                )
            else:
                query += sql.SQL(" ON CONFLICT DO NOTHING")
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params)
            conn.commit()
        return len(params)
