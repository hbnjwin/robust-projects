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
    parse_cn_datetime,
    split_symbol,
)


FUND_FLOW_VALUE_ALIASES = {
    "close": ["close", "price_close", "last_close"],
    "pct_chg": ["pct_chg", "change_percent", "change_pct", "pct_change"],
    "main_net": [
        "net_amount_main",
        "main_net_inflow_amount",
        "net_main_amount",
        "main_amount",
        "main_inflow_amount",
    ],
    "main_net_pct": [
        "net_ratio_main",
        "main_net_inflow_ratio",
        "main_ratio",
        "net_main_ratio",
        "main_inflow_ratio",
    ],
    "super_net": [
        "net_amount_super",
        "super_large_net_inflow_amount",
        "super_net_inflow_amount",
        "super_amount",
        "huge_amount",
        "extra_large_amount",
        "net_amount_xl",
    ],
    "super_net_pct": [
        "net_ratio_super",
        "super_large_net_inflow_ratio",
        "super_net_inflow_ratio",
        "super_ratio",
        "huge_ratio",
        "extra_large_ratio",
        "net_ratio_xl",
    ],
    "big_net": [
        "net_amount_large",
        "large_net_inflow_amount",
        "large_amount",
        "big_amount",
    ],
    "big_net_pct": [
        "net_ratio_large",
        "large_net_inflow_ratio",
        "large_ratio",
        "big_ratio",
    ],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="import_fund_flow.py")
    parser.add_argument("--symbols", required=True, help="comma-separated symbols such as 000001.SZ,600519.SH")
    parser.add_argument("--period", default="transactioncount1d", choices=["transactioncount1d", "transactioncount1m"])
    parser.add_argument("--start-time", default="")
    parser.add_argument("--end-time", default="")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--read-mode", default="auto", choices=["auto", "local", "market"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--pg-dsn",
        default=os.environ.get("QMT_BROKER_FUND_FLOW_PG_DSN")
        or os.environ.get("QMT_BROKER_BAR_ARCHIVE_PG_DSN")
        or os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
    )
    parser.add_argument("--pg-schema", default="public")
    parser.add_argument("--pg-table", default="stock_fund_flow")
    return parser


def build_fund_flow_row(symbol: str, period: str, record: dict[str, Any]) -> dict[str, Any]:
    clean = clean_symbol(symbol)
    code, exchange = split_symbol(clean)
    record_time = parse_cn_datetime(first_present(record, ["time", "stime", "trade_time", "date"]))
    trade_date = parse_cn_date(first_present(record, ["time", "stime", "trade_date", "date"]))
    if trade_date is None and record_time is not None:
        trade_date = record_time.date()
    row: dict[str, Any] = {
        "ts_code": clean,
        "trade_date": trade_date,
        "raw_json": json_ready(record),
    }
    for key, value in record.items():
        text_key = str(key).strip()
        if not text_key:
            continue
        normalized_value = value
        row.setdefault(text_key, normalized_value)
        row.setdefault(text_key.lower(), normalized_value)
    metrics = {column_name: first_present(record, aliases) for column_name, aliases in FUND_FLOW_VALUE_ALIASES.items()}
    for column_name, value in metrics.items():
        if value is None:
            continue
        row[column_name] = value
    return row


def read_fund_flow_rows(symbol: str, period: str, start_time: str, end_time: str, read_mode: str) -> tuple[list[dict[str, Any]], str]:
    from xtquant import xtdata  # type: ignore

    candidates = ["local", "market"] if read_mode == "auto" else [read_mode]
    last_mode = candidates[-1]
    for mode in candidates:
        if mode == "local":
            dataset = xtdata.get_local_data([], [symbol], period=period, start_time=start_time, end_time=end_time, count=-1)
        else:
            dataset = xtdata.get_market_data_ex([], [symbol], period=period, start_time=start_time, end_time=end_time, count=-1)
        rows = normalize_records(dataset.get(symbol) if isinstance(dataset, dict) else None)
        if rows:
            return rows, mode
        last_mode = mode
    return [], last_mode


def main() -> int:
    args = build_parser().parse_args()
    ensure_xtquant_importable(PROJECT_ROOT)
    from xtquant import xtdata  # type: ignore

    symbols = [clean_symbol(item) for item in str(args.symbols).split(",") if clean_symbol(item)]
    if not symbols:
        raise SystemExit("at least one symbol is required")
    store = DynamicPostgresUpsertStore(args.pg_dsn, schema=args.pg_schema, table=args.pg_table)
    if not args.dry_run and not store.enabled():
        raise SystemExit("pg dsn is required unless --dry-run is used")
    summary: dict[str, Any] = {
        "ok": True,
        "table": args.pg_table,
        "schema": args.pg_schema,
        "period": args.period,
        "read_mode": args.read_mode,
        "symbols": symbols,
        "downloaded": 0,
        "read_rows": 0,
        "written": 0,
        "read_sources": {},
        "sample": [],
    }
    for symbol in symbols:
        if not args.skip_download:
            xtdata.download_history_data(symbol, period=args.period, start_time=args.start_time, end_time=args.end_time)
            summary["downloaded"] += 1
        records, read_source = read_fund_flow_rows(symbol, args.period, args.start_time, args.end_time, args.read_mode)
        summary["read_sources"][symbol] = read_source
        rows = [build_fund_flow_row(symbol, args.period, record) for record in records]
        summary["read_rows"] += len(rows)
        if not summary["sample"] and rows:
            summary["sample"] = rows[:2]
        if not args.dry_run and rows:
            summary["written"] += store.upsert_rows(rows)
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
