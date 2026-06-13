from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FieldMapping:
    target_column: str
    json_index: int
    official_field: str
    official_label: str
    confidence: str
    note: str


SAFE_MAPPINGS = [
    FieldMapping(
        target_column="roe",
        json_index=17,
        official_field="net_roe",
        official_label="摊薄净资产收益率",
        confidence="high",
        note="与现有 stock_fundamentals.roe 高相关，且中位误差极小。",
    ),
    FieldMapping(
        target_column="gross_margin",
        json_index=19,
        official_field="gross_profit",
        official_label="毛利率",
        confidence="high",
        note="与 raw_9 数值一致，和现有 gross_margin 基本逐行相等。",
    ),
    FieldMapping(
        target_column="net_margin",
        json_index=20,
        official_field="net_profit",
        official_label="净利率",
        confidence="high",
        note="与现有 net_margin 基本逐行相等。",
    ),
    FieldMapping(
        target_column="debt_ratio",
        json_index=24,
        official_field="gear_ratio",
        official_label="资产负债比率",
        confidence="high",
        note="与现有 debt_ratio 基本逐行相等。",
    ),
    FieldMapping(
        target_column="revenue_growth",
        json_index=9,
        official_field="inc_revenue_rate",
        official_label="主营收入同比增长",
        confidence="high",
        note="与现有 revenue_growth 高相关，且大部分样本完全一致。",
    ),
    FieldMapping(
        target_column="profit_growth",
        json_index=10,
        official_field="du_profit_rate",
        official_label="净利润同比增长",
        confidence="high",
        note="与现有 profit_growth 高相关，且大部分样本完全一致。",
    ),
]


OPTIONAL_MAPPINGS = [
    FieldMapping(
        target_column="bps",
        json_index=1,
        official_field="s_fa_bps",
        official_label="每股净资产",
        confidence="medium",
        note="官方字段语义明确，但与现有 bps 存在部分口径差异，默认不回写。",
    ),
    FieldMapping(
        target_column="eps",
        json_index=2,
        official_field="s_fa_eps_basic",
        official_label="基本每股收益",
        confidence="medium",
        note="官方字段语义明确，但与现有 eps 存在明显口径差异，默认不回写。",
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="import_finance_dat_to_fundamentals.py")
    parser.add_argument(
        "--pg-dsn",
        default=os.environ.get("QMT_BROKER_FUNDAMENTALS_PG_DSN")
        or os.environ.get("QMT_BROKER_SECURITY_MASTER_PG_DSN")
        or os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
    )
    parser.add_argument("--pg-schema", default="public")
    parser.add_argument("--source-table", default="stock_finance_dat_raw")
    parser.add_argument("--target-table", default="stock_fundamentals")
    parser.add_argument("--dataset-id", type=int, default=7008)
    parser.add_argument("--apply", action="store_true", help="write safe fields back to stock_fundamentals")
    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="overwrite existing non-null values for the selected mapped fields",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="also include medium-confidence fields such as eps/bps",
    )
    parser.add_argument("--limit", type=int, default=0, help="limit source rows for sampling or staged rollout")
    return parser


def build_mappings(include_optional: bool) -> list[FieldMapping]:
    if not include_optional:
        return list(SAFE_MAPPINGS)
    return [*SAFE_MAPPINGS, *OPTIONAL_MAPPINGS]


def build_source_cte(schema: str, source_table: str, dataset_id: int, mappings: list[FieldMapping], limit: int) -> str:
    selected = ",\n        ".join(
        f"(r.raw_json->'values'->>{mapping.json_index})::double precision AS {mapping.target_column}"
        for mapping in mappings
    )
    limit_sql = f"\n    LIMIT {limit}" if limit > 0 else ""
    return f"""
WITH source AS (
    SELECT DISTINCT ON (r.ts_code, r.announce_date)
        r.ts_code,
        r.announce_date AS report_date,
        r.report_date AS publish_date,
        {selected}
    FROM {schema}.{source_table} r
    WHERE r.dataset_id = {dataset_id}
      AND r.raw_json ? 'values'
      AND r.announce_date IS NOT NULL
    ORDER BY r.ts_code, r.announce_date, r.report_date DESC NULLS LAST, r.record_no DESC
    {limit_sql}
)
"""


def build_non_null_filter(mappings: list[FieldMapping]) -> str:
    return " OR ".join(f"source.{mapping.target_column} IS NOT NULL" for mapping in mappings)


def build_insert_sql(schema: str, target_table: str, mappings: list[FieldMapping], force_overwrite: bool) -> str:
    mapped_columns = ", ".join(mapping.target_column for mapping in mappings)
    select_columns = ", ".join(f"source.{mapping.target_column}" for mapping in mappings)
    if force_overwrite:
        updates = ",\n        ".join(
            f"{mapping.target_column} = COALESCE(EXCLUDED.{mapping.target_column}, {target_table}.{mapping.target_column})"
            for mapping in mappings
        )
    else:
        updates = ",\n        ".join(
            f"{mapping.target_column} = COALESCE({target_table}.{mapping.target_column}, EXCLUDED.{mapping.target_column})"
            for mapping in mappings
        )
    non_null_filter = build_non_null_filter(mappings)
    return f"""
INSERT INTO {schema}.{target_table} (ts_code, report_date, {mapped_columns})
SELECT
    source.ts_code,
    source.report_date,
    {select_columns}
FROM source
WHERE {non_null_filter}
ON CONFLICT (ts_code, report_date) DO UPDATE SET
        {updates}
"""


def build_summary_sql(schema: str, target_table: str, mappings: list[FieldMapping]) -> str:
    update_counts = ",\n    ".join(
        f"count(*) FILTER (WHERE target.{mapping.target_column} IS NULL AND source.{mapping.target_column} IS NOT NULL)"
        f" AS fill_{mapping.target_column}"
        for mapping in mappings
    )
    source_value_counts = ",\n    ".join(
        f"count(*) FILTER (WHERE source.{mapping.target_column} IS NOT NULL) AS source_{mapping.target_column}"
        for mapping in mappings
    )
    return f"""
SELECT
    count(*) AS matched_rows,
    count(*) FILTER (WHERE target.ts_code IS NULL) AS insert_candidates,
    count(*) FILTER (WHERE target.ts_code IS NOT NULL) AS existing_rows,
    {source_value_counts},
    {update_counts}
FROM source
LEFT JOIN {schema}.{target_table} target
  USING (ts_code, report_date)
"""


def build_preview_sql(mappings: list[FieldMapping]) -> str:
    preview_columns = ",\n    ".join(
        f"source.{mapping.target_column} AS {mapping.target_column}" for mapping in mappings
    )
    return f"""
SELECT
    source.ts_code,
    source.report_date,
    source.publish_date,
    {preview_columns}
FROM source
WHERE {build_non_null_filter(mappings)}
ORDER BY source.ts_code, source.report_date
LIMIT 10
"""


def main() -> int:
    args = build_parser().parse_args()
    if not args.pg_dsn:
        raise SystemExit("pg dsn is required")

    mappings = build_mappings(args.include_optional)
    source_cte = build_source_cte(args.pg_schema, args.source_table, args.dataset_id, mappings, args.limit)
    summary_sql = source_cte + build_summary_sql(args.pg_schema, args.target_table, mappings)
    preview_sql = source_cte + build_preview_sql(mappings)
    insert_sql = source_cte + build_insert_sql(args.pg_schema, args.target_table, mappings, args.force_overwrite)

    import psycopg

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
        "dataset_id": args.dataset_id,
        "source_table": f"{args.pg_schema}.{args.source_table}",
        "target_table": f"{args.pg_schema}.{args.target_table}",
        "apply": args.apply,
        "force_overwrite": args.force_overwrite,
        "mappings": [
            {
                "target_column": mapping.target_column,
                "json_index": mapping.json_index,
                "official_field": mapping.official_field,
                "official_label": mapping.official_label,
                "confidence": mapping.confidence,
                "note": mapping.note,
            }
            for mapping in mappings
        ],
        "summary": dict(zip(summary_columns, summary_row)),
        "written": written,
        "preview": [dict(zip(preview_columns, row)) for row in preview_rows],
    }
    print(json.dumps(payload, ensure_ascii=False, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
