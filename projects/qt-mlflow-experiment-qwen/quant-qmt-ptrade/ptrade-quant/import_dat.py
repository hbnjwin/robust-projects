#!/usr/bin/env python3
"""
Import stock daily K-line data from .DAT binary files into PostgreSQL.

Usage:
    python import_dat.py 600390.DAT [600519.DAT ...]
    python import_dat.py *.DAT --host 127.0.0.1 --port 5432 --db quant --user postgres --password secret

File format (64 bytes/record, little-endian):
    offset  0: uint32  unix timestamp (seconds)
    offset  4: uint32  open  * 100
    offset  8: uint32  high  * 100
    offset 12: uint32  low   * 100
    offset 16: uint32  close * 100
    offset 20: uint32  reserved (0)
    offset 24: uint32  volume (lots, 1 lot = 100 shares)
    offset 28: uint32  constant 32764
    offset 32: uint32  amount (unit: 10 yuan)
    offset 36: uint32  reserved (0)
    offset 40: uint32  constant 15
    offset 44: float32 adjust factor (1.0 normally, changes on ex-dividend)
    offset 48: float32 USD/CNY exchange rate
    offset 52: uint32  prev_close * 100
    offset 56: uint32  reserved (0)
    offset 60: uint32  constant 32764
"""

from __future__ import annotations

import argparse
import struct
import sys
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
# 11 uint32, 2 float32, 3 uint32 = 64 bytes
RECORD_FMT = "<IIIIIIIIIIIffIII"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS stock_daily_kline (
    symbol       varchar(20)    NOT NULL,
    trade_date   date           NOT NULL,
    open         numeric(12, 2) NOT NULL,
    high         numeric(12, 2) NOT NULL,
    low          numeric(12, 2) NOT NULL,
    close        numeric(12, 2) NOT NULL,
    prev_close   numeric(12, 2),
    volume       bigint,
    amount       bigint,
    adjust_factor double precision,
    usd_rate     double precision,
    created_at   timestamptz    NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, trade_date)
);
"""

UPSERT_SQL = """
INSERT INTO stock_daily_kline
    (symbol, trade_date, open, high, low, close, prev_close, volume, amount, adjust_factor, usd_rate)
VALUES %s
ON CONFLICT (symbol, trade_date) DO UPDATE SET
    open          = EXCLUDED.open,
    high          = EXCLUDED.high,
    low           = EXCLUDED.low,
    close         = EXCLUDED.close,
    prev_close    = EXCLUDED.prev_close,
    volume        = EXCLUDED.volume,
    amount        = EXCLUDED.amount,
    adjust_factor = EXCLUDED.adjust_factor,
    usd_rate      = EXCLUDED.usd_rate
"""


def parse_dat(path: Path) -> list[tuple]:
    """Parse a .DAT file and return a list of row tuples."""
    symbol = path.stem.upper()
    data = path.read_bytes()

    if len(data) < HEADER_SIZE:
        raise ValueError(f"{path}: file too small ({len(data)} bytes)")

    body = data[HEADER_SIZE:]
    n = len(body) // RECORD_SIZE
    if n == 0:
        raise ValueError(f"{path}: no records found")

    rows = []
    for i in range(n):
        offset = i * RECORD_SIZE
        chunk = body[offset : offset + RECORD_SIZE]
        (
            ts, open_raw, high_raw, low_raw, close_raw,
            _r0, volume, _c1, amount_raw, _r1, _c2,
            adjust_factor, usd_rate,
            prev_close_raw, _r2, _c3,
        ) = struct.unpack_from(RECORD_FMT, chunk)

        trade_date = datetime.fromtimestamp(ts).date()  # local time (CST)
        rows.append((
            symbol,
            trade_date,
            round(open_raw / 100, 2),
            round(high_raw / 100, 2),
            round(low_raw / 100, 2),
            round(close_raw / 100, 2),
            round(prev_close_raw / 100, 2) if prev_close_raw else None,
            volume,
            amount_raw * 10,       # stored unit is 10 yuan
            float(adjust_factor),
            float(usd_rate),
        ))

    return rows


def import_files(files: list[Path], conn_params: dict) -> None:
    conn = psycopg2.connect(**conn_params)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()

        for path in files:
            try:
                rows = parse_dat(path)
            except Exception as e:
                print(f"  SKIP {path.name}: {e}", file=sys.stderr)
                continue

            with conn.cursor() as cur:
                execute_values(cur, UPSERT_SQL, rows)
            conn.commit()
            print(f"  OK   {path.name}: {len(rows)} records -> {rows[0][0]}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import .DAT K-line files into PostgreSQL")
    parser.add_argument("files", nargs="+", type=Path, help=".DAT file(s) to import")
    parser.add_argument("--host",     default="127.0.0.1")
    parser.add_argument("--port",     default=5432, type=int)
    parser.add_argument("--db",       default="quant", dest="database")
    parser.add_argument("--user",     default="postgres")
    parser.add_argument("--password", default="")
    args = parser.parse_args()

    files = [f for f in args.files if f.suffix.upper() == ".DAT"]
    if not files:
        print("No .DAT files found.", file=sys.stderr)
        sys.exit(1)

    conn_params = dict(
        host=args.host,
        port=args.port,
        dbname=args.database,
        user=args.user,
        password=args.password,
    )

    print(f"Connecting to {args.user}@{args.host}:{args.port}/{args.database}")
    print(f"Importing {len(files)} file(s)...")
    import_files(files, conn_params)
    print("Done.")


if __name__ == "__main__":
    main()
