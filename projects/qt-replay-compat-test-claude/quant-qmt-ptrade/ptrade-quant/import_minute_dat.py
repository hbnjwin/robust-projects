#!/usr/bin/env python3
"""
Import 1-minute K-line data from QMT/PTrade .DAT binary files into PostgreSQL.

Usage:
    python import_minute_dat.py E:/qmt/datadir/SH/60
    python import_minute_dat.py E:/qmt/datadir/SH/60 --host 192.168.68.229 --password limit123
    python import_minute_dat.py E:/qmt/datadir/SH/60 --market SH --workers 4

File format (64 bytes/record, little-endian):
    offset  0: uint32  unix timestamp (local CST, minute bar start time)
    offset  4: uint32  open  * 1000  (index points, 3 decimal places)
    offset  8: uint32  high  * 1000
    offset 12: uint32  low   * 1000
    offset 16: uint32  close * 1000
    offset 20: uint32  reserved (0)
    offset 24: uint32  volume (shares for stock, units for index)
    offset 28: uint32  constant 32764
    offset 32: uint32  amount (unit: 10 yuan)
    offset 36: uint32  reserved (0)
    offset 40: uint32  asset_type (15=stock, 0=index)
    offset 44: float32 adjust_factor (1.0 normally)
    offset 48: float32 1.0 for index, USD/CNY rate for stock
    offset 52: uint32  prev_close * 1000
    offset 56: uint32  reserved (0)
    offset 60: uint32  constant 32764
"""

from __future__ import annotations

import argparse
import struct
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

HEADER_SIZE = 8
RECORD_SIZE = 64
RECORD_FMT = "<IIIIIIIIIIIffIII"
PRICE_DIVISOR = 1000  # index points use /1000

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS kline_1min (
    symbol       varchar(20)    NOT NULL,
    market       varchar(10)    NOT NULL DEFAULT '',
    bar_time     timestamptz    NOT NULL,
    open         numeric(14, 3) NOT NULL,
    high         numeric(14, 3) NOT NULL,
    low          numeric(14, 3) NOT NULL,
    close        numeric(14, 3) NOT NULL,
    prev_close   numeric(14, 3),
    volume       bigint,
    amount       bigint,
    asset_type   smallint,
    adjust_factor double precision,
    PRIMARY KEY (symbol, bar_time)
);
CREATE INDEX IF NOT EXISTS kline_1min_bar_time_idx ON kline_1min (bar_time);
"""

UPSERT_SQL = """
INSERT INTO kline_1min
    (symbol, market, bar_time, open, high, low, close, prev_close,
     volume, amount, asset_type, adjust_factor)
VALUES %s
ON CONFLICT (symbol, bar_time) DO UPDATE SET
    open          = EXCLUDED.open,
    high          = EXCLUDED.high,
    low           = EXCLUDED.low,
    close         = EXCLUDED.close,
    prev_close    = EXCLUDED.prev_close,
    volume        = EXCLUDED.volume,
    amount        = EXCLUDED.amount,
    asset_type    = EXCLUDED.asset_type,
    adjust_factor = EXCLUDED.adjust_factor
"""


def parse_dat(path: Path, market: str) -> list[tuple]:
    symbol = path.stem.upper()
    data = path.read_bytes()

    if len(data) < HEADER_SIZE:
        raise ValueError(f"file too small ({len(data)} bytes)")

    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    if n == 0:
        raise ValueError("no records found")

    rows = []
    for i in range(n):
        chunk = body[i * RECORD_SIZE : (i + 1) * RECORD_SIZE]
        (
            ts, open_raw, high_raw, low_raw, close_raw,
            _r0, volume, _c1, amount_raw, _r1, asset_type,
            adjust_factor, _field48,
            prev_close_raw, _r2, _c3,
        ) = struct.unpack_from(RECORD_FMT, chunk)

        bar_time = datetime.fromtimestamp(ts)  # local CST
        rows.append((
            symbol,
            market,
            bar_time,
            round(open_raw  / PRICE_DIVISOR, 3),
            round(high_raw  / PRICE_DIVISOR, 3),
            round(low_raw   / PRICE_DIVISOR, 3),
            round(close_raw / PRICE_DIVISOR, 3),
            round(prev_close_raw / PRICE_DIVISOR, 3) if prev_close_raw else None,
            volume,
            amount_raw * 10,
            asset_type,
            float(adjust_factor),
        ))

    return rows


def import_one(path: Path, market: str, conn_params: dict) -> tuple[str, int]:
    """Import a single DAT file. Returns (filename, record_count) or raises."""
    rows = parse_dat(path, market)
    conn = psycopg2.connect(**conn_params)
    try:
        with conn.cursor() as cur:
            execute_values(cur, UPSERT_SQL, rows)
        conn.commit()
    finally:
        conn.close()
    return path.name, len(rows)


def import_directory(dat_dir: Path, market: str, conn_params: dict, workers: int) -> None:
    files = sorted(dat_dir.glob("*.DAT"))
    if not files:
        print(f"No .DAT files found in {dat_dir}", file=sys.stderr)
        sys.exit(1)

    # Create table once
    conn = psycopg2.connect(**conn_params)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()

    total = len(files)
    done = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(import_one, f, market, conn_params): f for f in files}
        for fut in as_completed(futures):
            path = futures[fut]
            try:
                name, count = fut.result()
                done += 1
                if done % 500 == 0 or done == total:
                    print(f"  [{done}/{total}] {name}: {count} bars")
            except Exception as e:
                errors += 1
                print(f"  SKIP {path.name}: {e}", file=sys.stderr)

    print(f"\nDone. {done} files imported, {errors} skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import 1-min .DAT K-line files into PostgreSQL")
    parser.add_argument("dir", type=Path, help="Directory containing .DAT files (e.g. E:/qmt/datadir/SH/60)")
    parser.add_argument("--market",   default="SH", help="Market code, e.g. SH or SZ (default: SH)")
    parser.add_argument("--host",     default="192.168.68.229")
    parser.add_argument("--port",     default=5432, type=int)
    parser.add_argument("--db",       default="quant", dest="database")
    parser.add_argument("--user",     default="postgres")
    parser.add_argument("--password", default="limit123")
    parser.add_argument("--workers",  default=4, type=int, help="Parallel import threads (default: 4)")
    args = parser.parse_args()

    if not args.dir.is_dir():
        print(f"Not a directory: {args.dir}", file=sys.stderr)
        sys.exit(1)

    conn_params = dict(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=args.password,
    )

    dat_files = list(args.dir.glob("*.DAT"))
    print(f"Connecting to {args.user}@{args.host}:{args.port}/{args.database}")
    print(f"Directory: {args.dir}")
    print(f"Market: {args.market}, Files: {len(dat_files)}, Workers: {args.workers}")
    import_directory(args.dir, args.market, conn_params, args.workers)


if __name__ == "__main__":
    main()
