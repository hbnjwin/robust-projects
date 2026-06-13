from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from qmt_broker.importer_utils import (  # noqa: E402
    DynamicPostgresUpsertStore,
    clean_symbol,
    ensure_xtquant_importable,
    first_present,
    json_ready,
    normalize_records,
    parse_cn_date,
    split_symbol,
)


CANONICAL_FUNDAMENTAL_FIELDS = {
    "eps": ["s_fa_eps_basic", "eps", "adjusted_earnings_per_share"],
    "bps": ["s_fa_bps", "bps"],
    "roe": ["du_return_on_equity", "equity_roe", "net_roe", "roe"],
    "roa": ["total_roe", "roa"],
    "gross_margin": ["sales_gross_profit", "gross_profit", "gross_margin"],
    "net_margin": ["net_profit", "net_margin"],
    "debt_ratio": ["gear_ratio", "debt_ratio"],
    "revenue_growth": ["inc_revenue_rate", "revenue_growth"],
    "profit_growth": ["du_profit_rate", "inc_net_profit_rate", "profit_growth"],
    "total_assets": ["total_assets"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="import_fundamentals.py")
    parser.add_argument("--symbols", required=True, help="comma-separated symbols such as 000001.SZ,600519.SH")
    parser.add_argument("--tables", default="Balance,Income,CashFlow,Pershareindex")
    parser.add_argument("--start-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--report-type", default="report_time", choices=["report_time", "announce_time"])
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--pg-dsn",
        default=os.environ.get("QMT_BROKER_FUNDAMENTALS_PG_DSN")
        or os.environ.get("QMT_BROKER_SECURITY_MASTER_PG_DSN")
        or os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
    )
    parser.add_argument("--pg-schema", default="public")
    parser.add_argument("--pg-table", default="stock_fundamentals")
    return parser


def build_fundamental_row(symbol: str, table_name: str, report_type: str, record: dict[str, Any]) -> dict[str, Any]:
    clean = clean_symbol(symbol)
    code, exchange = split_symbol(clean)
    report_date = parse_cn_date(first_present(record, ["m_timetag", "endDate", "report_date"]))
    announce_date = parse_cn_date(first_present(record, ["m_anntime", "declareDate", "announce_date"]))
    row: dict[str, Any] = {
        "ts_code": clean,
        "report_date": report_date,
        "raw_json": json_ready(record),
    }
    for key, value in record.items():
        text_key = str(key).strip()
        if not text_key:
            continue
        row.setdefault(text_key, value)
        row.setdefault(text_key.lower(), value)
    for target_field, candidates in CANONICAL_FUNDAMENTAL_FIELDS.items():
        value = first_present(record, candidates)
        if value is not None:
            row[target_field] = value
    return row


def merge_fundamental_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, Any], dict[str, Any]] = {}
    canonical_fields = set(CANONICAL_FUNDAMENTAL_FIELDS.keys())
    for row in rows:
        key = (str(row.get("ts_code") or ""), row.get("report_date"))
        if not key[0] or key[1] is None:
            continue
        target = merged.setdefault(
            key,
            {
                "ts_code": row["ts_code"],
                "report_date": row["report_date"],
            },
        )
        for field in canonical_fields:
            value = row.get(field)
            if value is not None and target.get(field) is None:
                target[field] = value
    return list(merged.values())


def main() -> int:
    args = build_parser().parse_args()
    ensure_xtquant_importable(PROJECT_ROOT)
    from xtquant import xtdata  # type: ignore

    symbols = [clean_symbol(item) for item in str(args.symbols).split(",") if clean_symbol(item)]
    tables = [str(item).strip() for item in str(args.tables).split(",") if str(item).strip()]
    if not symbols:
        raise SystemExit("at least one symbol is required")
    if not tables:
        raise SystemExit("at least one financial table is required")
    store = DynamicPostgresUpsertStore(args.pg_dsn, schema=args.pg_schema, table=args.pg_table)
    if not args.dry_run and not store.enabled():
        raise SystemExit("pg dsn is required unless --dry-run is used")
    if not args.skip_download:
        xtdata.download_financial_data(symbols, table_list=tables)
    dataset = xtdata.get_financial_data(
        symbols,
        table_list=tables,
        start_time=args.start_time,
        end_time=args.end_time,
        report_type=args.report_type,
    )
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        symbol_tables = dataset.get(symbol, {}) if isinstance(dataset, dict) else {}
        if not isinstance(symbol_tables, dict):
            continue
        for table_name in tables:
            table_records = normalize_records(symbol_tables.get(table_name))
            for record in table_records:
                rows.append(build_fundamental_row(symbol, table_name, args.report_type, record))
    merged_rows = merge_fundamental_rows(rows)
    written = 0 if args.dry_run or not merged_rows else store.upsert_rows(merged_rows)
    summary = {
        "ok": True,
        "table": args.pg_table,
        "schema": args.pg_schema,
        "symbols": symbols,
        "tables": tables,
        "read_rows": len(rows),
        "merged_rows": len(merged_rows),
        "written": written,
        "sample": merged_rows[:2],
    }
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
