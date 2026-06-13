from __future__ import annotations

import argparse
import json
import os


SAFE_COLUMNS = [
    "announce_date",
    "ocfps",
    "bps_official",
    "eps_basic",
    "eps_diluted",
    "roe",
    "gross_margin",
    "net_margin",
    "debt_ratio",
    "revenue_growth",
    "profit_growth",
    "total_capital",
    "circulating_capital",
    "total_assets",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sync_finance_dat_fundamentals.py")
    parser.add_argument(
        "--pg-dsn",
        default=os.environ.get("QMT_BROKER_FUNDAMENTALS_PG_DSN")
        or os.environ.get("QMT_BROKER_SECURITY_MASTER_PG_DSN")
        or os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
    )
    parser.add_argument("--pg-schema", default="public")
    parser.add_argument("--source-table", default="stock_finance_dat_raw")
    parser.add_argument("--target-table", default="stock_fundamentals")
    parser.add_argument("--apply", action="store_true", help="write merged safe fields into stock_fundamentals")
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="overwrite existing non-null values for the synced columns",
    )
    parser.add_argument("--limit", type=int, default=0, help="limit rows for staged rollout")
    return parser


def build_source_cte(schema: str, source_table: str, limit: int) -> str:
    limit_sql = f"\nLIMIT {limit}" if limit > 0 else ""
    return f"""
WITH source_7001 AS (
    SELECT DISTINCT ON (r.ts_code, r.announce_date)
        r.ts_code,
        r.announce_date AS report_date,
        r.report_date AS announce_date,
        (r.raw_json->'values'->>73)::double precision AS total_assets
    FROM {schema}.{source_table} r
    WHERE r.dataset_id = 7001
      AND r.raw_json ? 'values'
      AND r.announce_date IS NOT NULL
    ORDER BY r.ts_code, r.announce_date, r.report_date DESC NULLS LAST, r.record_no DESC
),
source_7004 AS (
    SELECT DISTINCT ON (r.ts_code, r.announce_date)
        r.ts_code,
        r.announce_date AS report_date,
        r.report_date AS announce_date,
        r.value_1::double precision AS total_capital,
        CASE
            WHEN COALESCE(r.value_4, 0) > 0 THEN r.value_4::double precision
            ELSE r.value_2::double precision
        END AS circulating_capital
    FROM {schema}.{source_table} r
    WHERE r.dataset_id = 7004
      AND r.announce_date IS NOT NULL
    ORDER BY r.ts_code, r.announce_date, r.report_date DESC NULLS LAST, r.record_no DESC
),
source_7008 AS (
    SELECT DISTINCT ON (r.ts_code, r.announce_date)
        r.ts_code,
        r.announce_date AS report_date,
        r.report_date AS announce_date,
        (r.raw_json->'values'->>0)::double precision AS ocfps,
        (r.raw_json->'values'->>1)::double precision AS bps_official,
        (r.raw_json->'values'->>2)::double precision AS eps_basic,
        (r.raw_json->'values'->>3)::double precision AS eps_diluted,
        (r.raw_json->'values'->>17)::double precision AS roe,
        (r.raw_json->'values'->>19)::double precision AS gross_margin,
        (r.raw_json->'values'->>20)::double precision AS net_margin,
        (r.raw_json->'values'->>24)::double precision AS debt_ratio,
        (r.raw_json->'values'->>9)::double precision AS revenue_growth,
        (r.raw_json->'values'->>10)::double precision AS profit_growth
    FROM {schema}.{source_table} r
    WHERE r.dataset_id = 7008
      AND r.raw_json ? 'values'
      AND r.announce_date IS NOT NULL
    ORDER BY r.ts_code, r.announce_date, r.report_date DESC NULLS LAST, r.record_no DESC
),
merged AS (
    SELECT
        COALESCE(s7008.ts_code, s7001.ts_code, s7004.ts_code) AS ts_code,
        COALESCE(s7008.report_date, s7001.report_date, s7004.report_date) AS report_date,
        COALESCE(s7008.announce_date, s7001.announce_date, s7004.announce_date) AS announce_date,
        s7008.ocfps,
        s7008.bps_official,
        s7008.eps_basic,
        s7008.eps_diluted,
        s7008.roe,
        s7008.gross_margin,
        s7008.net_margin,
        s7008.debt_ratio,
        s7008.revenue_growth,
        s7008.profit_growth,
        s7004.total_capital,
        s7004.circulating_capital,
        s7001.total_assets
    FROM source_7008 s7008
    FULL OUTER JOIN source_7001 s7001
      ON s7008.ts_code = s7001.ts_code
     AND s7008.report_date = s7001.report_date
    FULL OUTER JOIN source_7004 s7004
      ON COALESCE(s7008.ts_code, s7001.ts_code) = s7004.ts_code
     AND COALESCE(s7008.report_date, s7001.report_date) = s7004.report_date
    {limit_sql}
)
"""


def build_non_null_filter() -> str:
    return " OR ".join(f"merged.{column} IS NOT NULL" for column in SAFE_COLUMNS)


def build_summary_sql(schema: str, target_table: str) -> str:
    source_counts = ",\n    ".join(
        f"count(*) FILTER (WHERE merged.{column} IS NOT NULL) AS source_{column}" for column in SAFE_COLUMNS
    )
    fill_counts = ",\n    ".join(
        f"count(*) FILTER (WHERE target.{column} IS NULL AND merged.{column} IS NOT NULL) AS fill_{column}"
        for column in SAFE_COLUMNS
    )
    return f"""
SELECT
    count(*) AS matched_rows,
    count(*) FILTER (WHERE target.ts_code IS NULL) AS insert_candidates,
    count(*) FILTER (WHERE target.ts_code IS NOT NULL) AS existing_rows,
    {source_counts},
    {fill_counts}
FROM merged
LEFT JOIN {schema}.{target_table} target
  USING (ts_code, report_date)
"""


def build_preview_sql() -> str:
    preview_columns = ",\n    ".join(f"merged.{column}" for column in SAFE_COLUMNS)
    return f"""
SELECT
    merged.ts_code,
    merged.report_date,
    {preview_columns}
FROM merged
WHERE {build_non_null_filter()}
ORDER BY merged.ts_code, merged.report_date
LIMIT 10
"""


def build_insert_sql(schema: str, target_table: str, force_overwrite: bool) -> str:
    columns = ", ".join(SAFE_COLUMNS)
    values = ", ".join(f"merged.{column}" for column in SAFE_COLUMNS)
    if force_overwrite:
        updates = ",\n        ".join(
            f"{column} = COALESCE(EXCLUDED.{column}, {target_table}.{column})" for column in SAFE_COLUMNS
        )
    else:
        updates = ",\n        ".join(
            f"{column} = COALESCE({target_table}.{column}, EXCLUDED.{column})" for column in SAFE_COLUMNS
        )
    return f"""
INSERT INTO {schema}.{target_table} (ts_code, report_date, {columns})
SELECT
    merged.ts_code,
    merged.report_date,
    {values}
FROM merged
WHERE {build_non_null_filter()}
ON CONFLICT (ts_code, report_date) DO UPDATE SET
        {updates}
"""


def main() -> int:
    args = build_parser().parse_args()
    if not args.pg_dsn:
        raise SystemExit("pg dsn is required")

    import psycopg

    source_cte = build_source_cte(args.pg_schema, args.source_table, args.limit)
    summary_sql = source_cte + build_summary_sql(args.pg_schema, args.target_table)
    preview_sql = source_cte + build_preview_sql()
    insert_sql = source_cte + build_insert_sql(args.pg_schema, args.target_table, args.force_overwrite)

    with psycopg.connect(args.pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(summary_sql)
            summary_row = cur.fetchone()
            summary_columns = [desc.name for desc in cur.description]
            cur.execute(preview_sql)
            preview_rows = cur.fetchall()
            preview_columns = [desc.name for desc in cur.description]
            written = 0
            if args.apply:
                cur.execute(insert_sql)
                written = cur.rowcount or 0
        conn.commit()

    payload = {
        "ok": True,
        "source_table": f"{args.pg_schema}.{args.source_table}",
        "target_table": f"{args.pg_schema}.{args.target_table}",
        "apply": args.apply,
        "force_overwrite": args.force_overwrite,
        "columns": SAFE_COLUMNS,
        "summary": dict(zip(summary_columns, summary_row)),
        "written": written,
        "preview": [dict(zip(preview_columns, row)) for row in preview_rows],
    }
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
