"""
因子计算流水线
PG → DuckDB因子计算 → 截面标准化 → Parquet输出

用法:
    from factor_engine import FactorPipeline
    pipe = FactorPipeline()
    path = pipe.run(start_date="2016-01-01", end_date="2025-12-31")
"""
import os
import time
from pathlib import Path

import duckdb
import pandas as pd

# 项目根目录
_ROOT = Path(__file__).resolve().parent.parent
_SQL_DIR = Path(__file__).resolve().parent

# PG 配置（复用 config.py）
import sys
sys.path.insert(0, str(_ROOT))
from config import PG_CONFIG


# 不参与标准化的列
_META_COLS = {"ts_code", "trade_date", "close", "volume", "daily_return"}
_LABEL_COLS = {"label_3d", "label_5d", "label_10d"}
_SKIP_COLS = _META_COLS | _LABEL_COLS


class FactorPipeline:
    """一键因子计算流水线"""

    def __init__(self, db_path: str = ":memory:"):
        self.con = duckdb.connect(db_path)
        self._pg_attached = False

    def _attach_pg(self):
        if self._pg_attached:
            return
        self.con.execute("INSTALL postgres; LOAD postgres;")
        # 强制 127.0.0.1 避免 IPv6 ::1 被 pg_hba.conf 拒绝
        host = PG_CONFIG['host']
        if host == 'localhost':
            host = '127.0.0.1'
        pg_parts = [
            f"dbname={PG_CONFIG['dbname']}",
            f"user={PG_CONFIG['user']}",
            f"password={PG_CONFIG['password']}",
            f"host={host}",
        ]
        if 'port' in PG_CONFIG:
            pg_parts.append(f"port={PG_CONFIG['port']}")
        pg_str = " ".join(pg_parts)
        self.con.execute(f"ATTACH '{pg_str}' AS pg (TYPE POSTGRES, READ_ONLY)")
        self._pg_attached = True

    def _load_prices(
        self,
        start_date: str,
        end_date: str,
        ts_codes: list[str] | None = None,
    ):
        """从 PG 加载日线数据到 DuckDB 内存表 prices"""
        self._attach_pg()

        where_parts = [
            f"trade_date >= '{start_date}'",
            f"trade_date <= '{end_date}'",
        ]
        if ts_codes:
            codes_str = ",".join(f"'{c}'" for c in ts_codes)
            where_parts.append(f"ts_code IN ({codes_str})")

        where_clause = " AND ".join(where_parts)

        sql = f"""
        CREATE OR REPLACE TABLE prices AS
        SELECT ts_code, trade_date, open, high, low, close, vol AS volume
        FROM pg.public.daily_price
        WHERE {where_clause}
        ORDER BY ts_code, trade_date
        """
        self.con.execute(sql)
        count = self.con.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        stocks = self.con.execute("SELECT COUNT(DISTINCT ts_code) FROM prices").fetchone()[0]
        print(f"[load] {count:,} rows, {stocks} stocks ({start_date} ~ {end_date})")
        return count

    def _compute_factors(self):
        """执行因子计算 SQL，结果存入 raw_factors 表"""
        sql_path = _SQL_DIR / "alpha_factors.sql"
        sql_text = sql_path.read_text(encoding="utf-8")

        # 将 SELECT * FROM factors 改为 CREATE TABLE
        create_sql = f"CREATE OR REPLACE TABLE raw_factors AS\n{sql_text}"
        self.con.execute(create_sql)

        count = self.con.execute("SELECT COUNT(*) FROM raw_factors").fetchone()[0]
        cols = [
            desc[0]
            for desc in self.con.execute("DESCRIBE raw_factors").fetchall()
        ]
        factor_cols = [c for c in cols if c not in _SKIP_COLS]
        print(f"[factors] {count:,} rows × {len(factor_cols)} factors")
        return factor_cols

    def _normalize(self, factor_cols: list[str], method: str = "robust_zscore"):
        """截面标准化"""
        if method == "robust_zscore":
            self._robust_zscore_norm(factor_cols)
        elif method == "cs_rank":
            self._cs_rank_norm(factor_cols)
        else:
            raise ValueError(f"Unknown norm method: {method}")

        count = self.con.execute("SELECT COUNT(*) FROM normalized_factors").fetchone()[0]
        print(f"[norm] {count:,} rows, method={method}")

    def _robust_zscore_norm(self, factor_cols: list[str]):
        """
        Robust Z-Score: (x - median) / (MAD * 1.4826), clip [-3, 3]
        全部在一条 SQL 里完成，避免多次扫描。
        """
        # 1. 计算每日每因子的 median
        median_exprs = ",\n        ".join(
            f"MEDIAN({c}) AS med_{c}" for c in factor_cols
        )

        # 2. 计算每日每因子的 MAD
        mad_exprs = ",\n        ".join(
            f"MEDIAN(ABS(f.{c} - m.med_{c})) AS mad_{c}" for c in factor_cols
        )

        # 3. 标准化 + clip
        zscore_exprs = ",\n        ".join(
            f"GREATEST(-3.0, LEAST(3.0, "
            f"(f.{c} - m.med_{c}) / NULLIF(d.mad_{c} * 1.4826, 0)"
            f")) AS {c}"
            for c in factor_cols
        )

        # 标签列直接透传
        label_exprs = ", ".join(f"f.{c}" for c in sorted(_LABEL_COLS))

        sql = f"""
        CREATE OR REPLACE TABLE normalized_factors AS
        WITH medians AS (
            SELECT
                trade_date,
                {median_exprs}
            FROM raw_factors
            GROUP BY trade_date
        ),
        mads AS (
            SELECT
                f.trade_date,
                {mad_exprs}
            FROM raw_factors f
            JOIN medians m ON f.trade_date = m.trade_date
            GROUP BY f.trade_date
        )
        SELECT
            f.ts_code,
            f.trade_date,
            {zscore_exprs},
            {label_exprs}
        FROM raw_factors f
        JOIN medians m ON f.trade_date = m.trade_date
        JOIN mads d ON f.trade_date = d.trade_date
        ORDER BY f.ts_code, f.trade_date
        """
        self.con.execute(sql)

    def _cs_rank_norm(self, factor_cols: list[str]):
        """
        CS Rank Norm: (PERCENT_RANK() - 0.5) * 3.46
        """
        rank_exprs = ",\n        ".join(
            f"(PERCENT_RANK() OVER (PARTITION BY trade_date ORDER BY {c}) - 0.5) * 3.46 AS {c}"
            for c in factor_cols
        )
        label_exprs = ", ".join(sorted(_LABEL_COLS))

        sql = f"""
        CREATE OR REPLACE TABLE normalized_factors AS
        SELECT
            ts_code,
            trade_date,
            {rank_exprs},
            {label_exprs}
        FROM raw_factors
        ORDER BY ts_code, trade_date
        """
        self.con.execute(sql)

    def _export(self, output_path: str):
        """导出为 Parquet"""
        output_path = str(Path(output_path).resolve())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.con.execute(
       f"COPY normalized_factors TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"[export] {output_path} ({size_mb:.1f} MB)")

    def run(
        self,
        start_date: str = "2016-01-01",
        end_date: str = "2025-12-31",
        ts_codes: list[str] | None = None,
        norm_method: str = "robust_zscore",
        output_path: str | None = None,
    ) -> str:
        """
        一键执行: PG → 因子计算 → 截面标准化 → Parquet

        Parameters
        ----------
        start_date : 开始日期
        end_date : 结束日期
        ts_codes : 股票列表, None=全市场
        norm_method : 标准化方法 (robust_zscore | cs_rank)
        output_path : 输出路径, None=自动生成

        Returns
        -------
        str : 输出文件路径
        """
        if output_path is None:
            output_path = str(
                _ROOT / "data" / f"factors_{norm_method}_{start_date}_{end_date}.parquet"
            )

        t0 = time.time()
        print(f"{'='*60}")
        print(f"Factor Pipeline: {start_date} ~ {end_date}")
        print(f"{'='*60}")

        # Step 1: 加载数据
        row_count = self._load_prices(start_date, end_date, ts_codes)
        if row_count == 0:
            print("[WARN] No data loaded, aborting.")
            return ""

        # Step 2: 计算因子
        factor_cols = self._compute_factors()

        # Step 3: 截面标准化
        self._normalize(factor_cols, method=norm_method)

        # Step 4: 导出
        self._export(output_path)

        elapsed = time.time() - t0
        print(f"{'='*60}")
        print(f"Done in {elapsed:.1f}s")
        print(f"{'='*60}")

        return output_path

    def run_raw(
        self,
        start_date: str = "2016-01-01",
        end_date: str = "2025-12-31",
        ts_codes: list[str] | None = None,
        output_path: str | None = None,
    ) -> str:
        """
        只计算因子，不做标准化（用于调试/IC分析）
        """
        if output_path is None:
            output_path = str(
                _ROOT / "data" / f"factors_raw_{start_date}_{end_date}.parquet"
            )

        t0 = time.time()
        row_count = self._load_prices(start_date, end_date, ts_codes)
        if row_count == 0:
            return ""

        self._compute_factors()

        # 直接导出 raw_factors
        output_path = str(Path(output_path).resolve())
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        self.con.execute(
            f"COPY raw_factors TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f"[export raw] {output_path} ({size_mb:.1f} MB) in {time.time()-t0:.1f}s")
        return output_path

    def query(self, sql: str) -> pd.DataFrame:
        """执行任意 SQL（调试用）"""
        return self.con.execute(sql).fetchdf()

    def close(self):
        self.con.close()


# ── CLI 入口 ──

def build_parser():
    """构建 CLI 参数解析器"""
    import argparse
    parser = argparse.ArgumentParser(description="Factor Pipeline")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--norm", default="robust_zscore", choices=["robust_zscore", "cs_rank"])
    parser.add_argument("--output", default=None)
    parser.add_argument("--raw", action="store_true", help="Only compute raw factors (no normalization)")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    pipe = FactorPipeline()
    if args.raw:
        pipe.run_raw(start_date=args.start, end_date=args.end, output_path=args.output)
    else:
        pipe.run(
            start_date=args.start,
            end_date=args.end,
            norm_method=args.norm,
            output_path=args.output,
        )
    pipe.close()
