from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from qmt_broker.finance_dat_parser import parse_finance_dat
from qmt_broker.importer_utils import DynamicPostgresUpsertStore, json_ready


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="import_finance_dat.py")
    parser.add_argument("--path", help="single dat file path, such as 600050_7004.DAT")
    parser.add_argument("--data-dir", help="Finance root directory, such as E:\\qmt\\datadir\\Finance")
    parser.add_argument(
        "--dataset-ids",
        default="7004,7005",
        help="comma-separated dataset ids; empty means all filenames that parser supports",
    )
    parser.add_argument("--limit-files", type=int, default=0, help="max files to parse when using --data-dir")
    parser.add_argument("--strict", action="store_true", help="stop on first unsupported or malformed dat file")
    parser.add_argument("--batch-size", type=int, default=500, help="rows per upsert batch when writing to postgres")
    parser.add_argument("--log-every", type=int, default=25, help="print parse progress every N files")
    parser.add_argument("--quiet", action="store_true", help="suppress progress logs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--pg-dsn",
        default=os.environ.get("QMT_BROKER_FUNDAMENTALS_PG_DSN")
        or os.environ.get("QMT_BROKER_SECURITY_MASTER_PG_DSN")
        or os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
    )
    parser.add_argument("--pg-schema", default="public")
    parser.add_argument("--pg-table", default="stock_finance_dat_raw")
    return parser


def discover_files(data_dir: Path, dataset_ids: list[int], limit_files: int) -> list[Path]:
    files = sorted(path for path in data_dir.rglob("*.DAT") if path.is_file())
    if dataset_ids:
        suffixes = {f"_{dataset_id}".upper() for dataset_id in dataset_ids}
        files = [path for path in files if Path(path).stem.upper().endswith(tuple(suffixes))]
    if limit_files > 0:
        return files[:limit_files]
    return files


def record_to_row(record: Any) -> dict[str, object]:
    return {
        "ts_code": record.ts_code,
        "market": record.market,
        "dataset_id": record.dataset_id,
        "record_no": record.record_no,
        "announce_date": record.announce_date,
        "report_date": record.report_date,
        "value_1": record.value_1,
        "value_2": record.value_2,
        "value_3": record.value_3,
        "value_4": record.value_4,
        "value_5": record.value_5,
        "value_6": record.value_6,
        "flag_1": record.flag_1,
        "flag_2": record.flag_2,
        "file_name": record.file_name,
        "file_size": record.file_size,
        "raw_json": json_ready(record.raw_json),
    }


def log(message: str, *, quiet: bool) -> None:
    if not quiet:
        print(message, file=sys.stderr, flush=True)


def batched(rows: list[dict[str, object]], batch_size: int) -> list[list[dict[str, object]]]:
    if batch_size <= 0:
        return [rows]
    return [rows[index : index + batch_size] for index in range(0, len(rows), batch_size)]


def main() -> int:
    args = build_parser().parse_args()
    dataset_ids = [int(item.strip()) for item in str(args.dataset_ids).split(",") if item.strip()]
    if not args.path and not args.data_dir:
        raise SystemExit("either --path or --data-dir is required")

    if args.path:
        files = [Path(args.path)]
    else:
        files = discover_files(Path(args.data_dir), dataset_ids, args.limit_files)

    if not files:
        raise SystemExit("no dat files found")

    parsed_files = []
    skipped_files: list[dict[str, str]] = []
    total_rows = 0
    for index, path in enumerate(files, start=1):
        try:
            parsed_file = parse_finance_dat(path)
            parsed_files.append(parsed_file)
            total_rows += len(parsed_file.records)
            if index == 1 or index == len(files) or (args.log_every > 0 and index % args.log_every == 0):
                log(
                    f"[parse] files={index}/{len(files)} rows={total_rows} current={path.name}",
                    quiet=args.quiet,
                )
        except Exception as exc:
            if args.strict:
                raise
            skipped_files.append({"path": str(path), "error": str(exc)})
            log(f"[skip] {path} :: {exc}", quiet=args.quiet)
    rows = [record_to_row(record) for parsed_file in parsed_files for record in parsed_file.records]

    store = DynamicPostgresUpsertStore(args.pg_dsn, schema=args.pg_schema, table=args.pg_table)
    if not args.dry_run and not store.enabled():
        raise SystemExit("pg dsn is required unless --dry-run is used")
    written = 0
    if not args.dry_run and rows:
        batches = batched(rows, args.batch_size)
        for index, batch in enumerate(batches, start=1):
            batch_written = store.upsert_rows(batch)
            written += batch_written
            log(
                f"[write] batches={index}/{len(batches)} written={written}/{len(rows)} rows",
                quiet=args.quiet,
            )

    summary = {
        "ok": True,
        "files_scanned": len(files),
        "files_parsed": len(parsed_files),
        "files_skipped": len(skipped_files),
        "rows": len(rows),
        "written": written,
        "datasets": sorted({parsed_file.dataset_id for parsed_file in parsed_files}),
        "sample_files": [
            {
                "path": str(parsed_file.path),
                "dataset_id": parsed_file.dataset_id,
                "record_size": parsed_file.record_size,
                "records": len(parsed_file.records),
            }
            for parsed_file in parsed_files[:5]
        ],
        "skipped": skipped_files[:10],
        "sample_rows": rows[:5],
    }
    print(json.dumps(summary, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
