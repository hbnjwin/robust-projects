import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from qmt_broker.providers.base import MarketDataProvider


@dataclass
class SecurityMasterSyncOptions:
    sectors: Sequence[str] = ()
    include_detail: bool = True
    dry_run: bool = False
    schema: str = "public"
    table: str = "security_master_cn"
    dsn: str = ""


class PostgresSecurityMasterStore:
    def __init__(self, dsn: str, schema: str = "public", table: str = "security_master_cn") -> None:
        self._dsn = str(dsn or "").strip()
        self._schema = str(schema or "public").strip() or "public"
        self._table = str(table or "security_master_cn").strip() or "security_master_cn"

    def enabled(self) -> bool:
        return bool(self._dsn)

    def upsert_records(self, rows: Iterable[Dict[str, object]]) -> int:
        normalized = [row for row in (_normalize_security_master_row(item) for item in rows) if row is not None]
        if not normalized:
            return 0
        if not self.enabled():
            raise RuntimeError("security master store is disabled")
        try:
            import psycopg
            from psycopg import sql
            from psycopg.types.json import Jsonb
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc
        query = sql.SQL(
            """
            INSERT INTO {}.{} (
              ts_code,
              symbol,
              exchange,
              name,
              instrument_type,
              product_name,
              list_date,
              delist_date,
              is_active,
              sector_names,
              import_source,
              raw_json
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (ts_code) DO UPDATE
            SET
              symbol = EXCLUDED.symbol,
              exchange = EXCLUDED.exchange,
              name = EXCLUDED.name,
              instrument_type = EXCLUDED.instrument_type,
              product_name = EXCLUDED.product_name,
              list_date = EXCLUDED.list_date,
              delist_date = EXCLUDED.delist_date,
              is_active = EXCLUDED.is_active,
              sector_names = EXCLUDED.sector_names,
              import_source = EXCLUDED.import_source,
              raw_json = EXCLUDED.raw_json,
              updated_at = NOW()
            """
        ).format(sql.Identifier(self._schema), sql.Identifier(self._table))
        params = [
            (
                row["ts_code"],
                row["symbol"],
                row["exchange"],
                row["name"],
                row["instrument_type"],
                row["product_name"],
                row["list_date"],
                row["delist_date"],
                row["is_active"],
                row["sector_names"],
                row["import_source"],
                Jsonb(row["raw_json"]),
            )
            for row in normalized
        ]
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params)
            conn.commit()
        return len(normalized)


def sync_security_master(
    provider: MarketDataProvider,
    store: PostgresSecurityMasterStore,
    options: SecurityMasterSyncOptions,
) -> Dict[str, object]:
    sectors = [str(item or "").strip() for item in options.sectors if str(item or "").strip()]
    if not sectors:
        sectors = provider.default_security_master_sectors()
    sectors = list(dict.fromkeys(sectors))
    sector_symbol_map: Dict[str, List[str]] = {}
    for sector in sectors:
        symbols = provider.get_stock_list_in_sector(sector)
        if symbols:
            sector_symbol_map[sector] = list(dict.fromkeys(symbols))
    merged_symbols = sorted({symbol for symbols in sector_symbol_map.values() for symbol in symbols})
    rows: List[Dict[str, object]] = []
    for symbol in merged_symbols:
        detail = provider.get_instrument_detail(symbol) if options.include_detail else {}
        rows.append(
            build_security_master_row(
                symbol,
                detail=detail,
                sector_names=[sector for sector, symbols in sector_symbol_map.items() if symbol in symbols],
                import_source=provider.name(),
            )
        )
    written = 0
    if rows and not options.dry_run:
        written = store.upsert_records(rows)
    return {
        "ok": True,
        "provider": provider.name(),
        "sector_count": len(sectors),
        "sectors": sectors,
        "symbol_count": len(merged_symbols),
        "written": written,
        "dry_run": bool(options.dry_run),
        "sample": rows[:3],
    }


def build_security_master_row(
    symbol: str,
    *,
    detail: Dict[str, object],
    sector_names: Sequence[str],
    import_source: str,
) -> Dict[str, object]:
    clean_symbol = str(symbol or "").strip().upper()
    base_symbol, exchange = _split_symbol(clean_symbol)
    list_date = _parse_yyyymmdd(detail.get("OpenDate"))
    delist_date = _parse_yyyymmdd(detail.get("ExpireDate"))
    name = str(detail.get("InstrumentName") or detail.get("name") or clean_symbol)
    instrument_type = str(detail.get("ProductID") or detail.get("InstrumentType") or "stock")
    product_name = str(detail.get("ProductName") or detail.get("product_name") or "")
    return {
        "ts_code": clean_symbol,
        "symbol": base_symbol,
        "exchange": str(detail.get("ExchangeID") or exchange),
        "name": name,
        "instrument_type": instrument_type,
        "product_name": product_name,
        "list_date": list_date,
        "delist_date": delist_date,
        "is_active": delist_date is None,
        "sector_names": list(dict.fromkeys(str(item).strip() for item in sector_names if str(item).strip())),
        "import_source": str(import_source or ""),
        "raw_json": _json_ready(detail),
    }


def _normalize_security_master_row(row: Dict[str, object]) -> Dict[str, object] | None:
    ts_code = str(row.get("ts_code") or "").strip().upper()
    if not ts_code:
        return None
    sector_names = row.get("sector_names")
    if not isinstance(sector_names, list):
        sector_names = []
    return {
        "ts_code": ts_code,
        "symbol": str(row.get("symbol") or ts_code.split(".", 1)[0]),
        "exchange": str(row.get("exchange") or ""),
        "name": str(row.get("name") or ts_code),
        "instrument_type": str(row.get("instrument_type") or "stock"),
        "product_name": str(row.get("product_name") or ""),
        "list_date": row.get("list_date"),
        "delist_date": row.get("delist_date"),
        "is_active": bool(row.get("is_active", True)),
        "sector_names": sector_names,
        "import_source": str(row.get("import_source") or ""),
        "raw_json": _json_ready(row.get("raw_json") if isinstance(row.get("raw_json"), dict) else {}),
    }


def _split_symbol(symbol: str) -> tuple[str, str]:
    if "." not in symbol:
        return symbol, ""
    code, exchange = symbol.split(".", 1)
    return code, exchange


def _parse_yyyymmdd(value: object):
    text = str(value or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def _json_ready(payload: Dict[str, object]) -> Dict[str, object]:
    encoded = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    return encoded if isinstance(encoded, dict) else {}
