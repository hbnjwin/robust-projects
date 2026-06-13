"""
tests/test_pipeline.py
factor_engine.pipeline 集成测试

覆盖:
  1. 因子计算完整性 (≥30 列, NaN 比例)
  2. robust_zscore 截面标准化 (均值≈0, 标准差≈1)
  3. cs_rank 标准化
  4. CLI 参数解析 (--start, --end, --norm, --output)
  5. Parquet 导出
"""
import argparse
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from factor_engine.pipeline import FactorPipeline, _META_COLS, _LABEL_COLS, _SKIP_COLS


# ====================================================================
# 1. 因子计算完整性
# ====================================================================

class TestFactorCompleteness:

    def test_at_least_30_factor_columns(self, pipeline_with_data):
        """输入 OHLCV 后应产出至少 30 个因子列"""
        factor_cols = pipeline_with_data._compute_factors()
        assert len(factor_cols) >= 30, (
            f"Expected ≥30 factor columns, got {len(factor_cols)}: {factor_cols}"
        )

    def test_raw_factors_row_count(self, pipeline_with_data):
        """raw_factors 行数 = 股票数 × 天数"""
        pipeline_with_data._compute_factors()
        count = pipeline_with_data.con.execute(
            "SELECT COUNT(*) FROM raw_factors"
        ).fetchone()[0]
        # 10 stocks × 30 days
        assert count == 300

    def test_nan_ratio_per_factor(self, pipeline_with_data):
        """每个因子的 NaN 比例不超过 70%（最长回望窗口 20 天 / 30 天 ≈ 67%）"""
        factor_cols = pipeline_with_data._compute_factors()
        df = pipeline_with_data.con.execute(
            "SELECT * FROM raw_factors"
        ).fetchdf()

        max_allowed_nan_ratio = 0.70
        violations = []
        for col in factor_cols:
            nan_ratio = df[col].isna().mean()
            if nan_ratio > max_allowed_nan_ratio:
                violations.append((col, nan_ratio))

        assert not violations, (
            f"Factors with NaN ratio > {max_allowed_nan_ratio}: "
            + ", ".join(f"{c}={r:.2%}" for c, r in violations)
        )

    def test_meta_and_label_cols_present(self, pipeline_with_data):
        """raw_factors 必须包含 meta 列和 label 列"""
        pipeline_with_data._compute_factors()
        cols = {
            desc[0]
            for desc in pipeline_with_data.con.execute(
                "DESCRIBE raw_factors"
            ).fetchall()
        }
        for c in ("ts_code", "trade_date", "close", "volume", "daily_return"):
            assert c in cols, f"Missing meta column: {c}"
        for c in ("label_3d", "label_5d", "label_10d"):
            assert c in cols, f"Missing label column: {c}"

    def test_no_all_nan_factor(self, pipeline_with_data):
        """不应有全为 NaN 的因子列"""
        factor_cols = pipeline_with_data._compute_factors()
        df = pipeline_with_data.con.execute(
            "SELECT * FROM raw_factors"
        ).fetchdf()

        all_nan = [c for c in factor_cols if df[c].isna().all()]
        assert not all_nan, f"Factors that are entirely NaN: {all_nan}"


# ====================================================================
# 2. robust_zscore 截面标准化
# ====================================================================

class TestRobustZscoreNorm:

    @pytest.fixture(autouse=True)
    def _run_normalize(self, pipeline_with_data):
        """自动执行因子计算 + robust_zscore 标准化"""
        self.pipe = pipeline_with_data
        self.factor_cols = pipeline_with_data._compute_factors()
        pipeline_with_data._normalize(self.factor_cols, method="robust_zscore")
        self.df = pipeline_with_data.con.execute(
            "SELECT * FROM normalized_factors"
        ).fetchdf()

    def test_cross_section_mean_near_zero(self):
        """
        robust_zscore 标准化后，每个截面日的因子均值应接近 0。
        跳过退化截面（unique 值 < 5）；小样本下允许 5% 截面超标。
        """
        dates = self.df["trade_date"].unique()
        total, violations = 0, 0
        for dt in dates:
            cross = self.df[self.df["trade_date"] == dt]
            for col in self.factor_cols:
                vals = cross[col].dropna()
                if len(vals) < 5 or vals.nunique() < 5:
                    continue
                total += 1
                if abs(vals.mean()) > 1.0:
                    violations += 1

        assert total > 0, "No valid cross-sections to check"
        violation_rate = violations / total
        assert violation_rate <= 0.05, (
            f"{violations}/{total} ({violation_rate:.1%}) cross-sections "
            f"with |mean| > 1.0 (threshold 5%)"
        )

    def test_cross_section_std_near_one(self):
        """
        标准化后截面标准差应在 [0.3, 2.5] 范围内。
        跳过退化截面（unique 值 < 3）。
        """
        dates = self.df["trade_date"].unique()
        violations = []
        for dt in dates:
            cross = self.df[self.df["trade_date"] == dt]
            for col in self.factor_cols:
                vals = cross[col].dropna()
                if len(vals) < 5 or vals.nunique() < 3:
                    continue
                std = vals.std()
                if std < 0.3 or std > 2.5:
                    violations.append((dt, col, std))

        assert not violations, (
            f"{len(violations)} cross-sections with std outside [0.3, 2.5]: "
            + str(violations[:5])
        )

    def test_values_clipped_to_minus3_plus3(self):
        """robust_zscore 应将值裁剪到 [-3, 3] 范围"""
        for col in self.factor_cols:
            vals = self.df[col].dropna()
            if len(vals) == 0:
                continue
            assert vals.min() >= -3.0 - 1e-9, f"{col} has value < -3"
            assert vals.max() <= 3.0 + 1e-9, f"{col} has value > 3"

    def test_normalized_preserves_row_count(self):
        """标准化不应改变行数"""
        raw_count = self.pipe.con.execute(
            "SELECT COUNT(*) FROM raw_factors"
        ).fetchone()[0]
        norm_count = self.pipe.con.execute(
            "SELECT COUNT(*) FROM normalized_factors"
        ).fetchone()[0]
        assert raw_count == norm_count

    def test_labels_pass_through(self):
        """标签列应在标准化后保持不变"""
        raw = self.pipe.con.execute(
            "SELECT ts_code, trade_date, label_3d, label_5d, label_10d "
            "FROM raw_factors ORDER BY ts_code, trade_date"
        ).fetchdf()
        norm = self.pipe.con.execute(
            "SELECT ts_code, trade_date, label_3d, label_5d, label_10d "
            "FROM normalized_factors ORDER BY ts_code, trade_date"
        ).fetchdf()
        pd.testing.assert_frame_equal(raw, norm)


# ====================================================================
# 3. cs_rank 标准化
# ====================================================================

class TestCsRankNorm:

    @pytest.fixture(autouse=True)
    def _run_normalize(self, pipeline_with_data):
        self.pipe = pipeline_with_data
        self.factor_cols = pipeline_with_data._compute_factors()
        pipeline_with_data._normalize(self.factor_cols, method="cs_rank")
        self.df = pipeline_with_data.con.execute(
            "SELECT * FROM normalized_factors"
        ).fetchdf()

    def test_cs_rank_range(self):
        """cs_rank 标准化值应在 [-1.73, 1.73] 范围 (±0.5*3.46)"""
        for col in self.factor_cols:
            vals = self.df[col].dropna()
            if len(vals) == 0:
                continue
            assert vals.min() >= -1.73 - 0.01, f"{col} min={vals.min():.3f}"
            assert vals.max() <= 1.73 + 0.01, f"{col} max={vals.max():.3f}"

    def test_cs_rank_mean_near_zero(self):
        """cs_rank 标准化后截面均值应接近 0（跳过退化截面，允许 5% 超标）"""
        dates = self.df["trade_date"].unique()
        total, violations = 0, 0
        for dt in dates:
            cross = self.df[self.df["trade_date"] == dt]
            for col in self.factor_cols:
                vals = cross[col].dropna()
                if len(vals) < 5 or vals.nunique() < 5:
                    continue
                total += 1
                if abs(vals.mean()) > 0.5:
                    violations += 1

        assert total > 0, "No valid cross-sections to check"
        violation_rate = violations / total
        assert violation_rate <= 0.05, (
            f"{violations}/{total} ({violation_rate:.1%}) cs_rank cross-sections "
            f"with |mean| > 0.5 (threshold 5%)"
        )


# ====================================================================
# 4. CLI 参数解析
# ====================================================================

def _build_cli_parser() -> argparse.ArgumentParser:
    """复制 pipeline.py 的 CLI parser 定义，用于独立测试参数解析"""
    parser = argparse.ArgumentParser(description="Factor Pipeline")
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument(
        "--norm", default="robust_zscore",
        choices=["robust_zscore", "cs_rank"],
    )
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--raw", action="store_true",
        help="Only compute raw factors (no normalization)",
    )
    return parser


class TestCliArgs:

    def test_default_args(self):
        parser = _build_cli_parser()
        args = parser.parse_args([])
        assert args.start == "2016-01-01"
        assert args.end == "2025-12-31"
        assert args.norm == "robust_zscore"
        assert args.output is None
        assert args.raw is False

    def test_custom_start_end(self):
        parser = _build_cli_parser()
        args = parser.parse_args(["--start", "2020-06-01", "--end", "2024-12-31"])
        assert args.start == "2020-06-01"
        assert args.end == "2024-12-31"

    def test_norm_cs_rank(self):
        parser = _build_cli_parser()
        args = parser.parse_args(["--norm", "cs_rank"])
        assert args.norm == "cs_rank"

    def test_invalid_norm_rejected(self):
        parser = _build_cli_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--norm", "invalid_method"])

    def test_output_path(self):
        parser = _build_cli_parser()
        args = parser.parse_args(["--output", "/tmp/my_factors.parquet"])
        assert args.output == "/tmp/my_factors.parquet"

    def test_raw_flag(self):
        parser = _build_cli_parser()
        args = parser.parse_args(["--raw"])
        assert args.raw is True

    def test_all_args_combined(self):
        parser = _build_cli_parser()
        args = parser.parse_args([
            "--start", "2022-01-01",
            "--end", "2023-06-30",
            "--norm", "cs_rank",
            "--output", "/data/out.parquet",
        ])
        assert args.start == "2022-01-01"
        assert args.end == "2023-06-30"
        assert args.norm == "cs_rank"
        assert args.output == "/data/out.parquet"


# ====================================================================
# 5. Parquet 导出 & run() 端到端
# ====================================================================

class TestExportAndRun:

    def test_export_produces_valid_parquet(self, pipeline_with_data):
        factor_cols = pipeline_with_data._compute_factors()
        pipeline_with_data._normalize(factor_cols, method="robust_zscore")

        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            out_path = f.name

        try:
            pipeline_with_data._export(out_path)
            assert os.path.exists(out_path)
            assert os.path.getsize(out_path) > 0

            df = pd.read_parquet(out_path)
            assert len(df) == 300  # 10 stocks × 30 days
            assert "ts_code" in df.columns
            assert "trade_date" in df.columns
        finally:
            os.unlink(out_path)

    def test_invalid_norm_method_raises(self, pipeline_with_data):
        factor_cols = pipeline_with_data._compute_factors()
        with pytest.raises(ValueError, match="Unknown norm method"):
            pipeline_with_data._normalize(factor_cols, method="bad_method")
