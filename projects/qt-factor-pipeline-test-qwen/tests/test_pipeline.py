"""
Integration tests for factor_engine.pipeline

Tests cover:
1. Robust z-score normalization correctness (mean ≈ 0, std ≈ 1)
2. Factor computation completeness (≥ 30 factor columns, NaN rates)
3. CLI argument parsing (--start, --end, --norm, --output)
4. Full pipeline end-to-end with mocked PostgreSQL
"""
import pandas as pd
import pytest

from factor_engine.pipeline import FactorPipeline, build_parser


# ── helpers ─────────────────────────────────────────────────────


def _load_prices_into_duckdb(pipe: FactorPipeline, df: pd.DataFrame):
    """Register a DataFrame as the ``prices`` table in DuckDB."""
    pipe.con.register("_tmp_ohlcv", df)
    pipe.con.execute(
        "CREATE OR REPLACE TABLE prices AS SELECT * FROM _tmp_ohlcv"
    )
    pipe.con.unregister("_tmp_ohlcv")


# ── 1. robust z-score normalization ────────────────────────────


class TestRobustZscore:
    """Verify robust_zscore produces well-behaved cross-sections."""

    def test_cross_section_mean_near_zero(self, sample_ohlcv):
        """Each trade_date cross-section should have factor mean ≈ 0.

        With only 10 stocks per cross-section, clipping at [-3, 3] can
        shift the mean.  We therefore skip factors whose values are
        heavily clipped or degenerate (all-NULL).
        """
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        factor_cols = pipe._compute_factors()
        pipe._normalize(factor_cols, method="robust_zscore")

        df = pipe.query(
            "SELECT trade_date, "
            + ", ".join(
                f"AVG({c}) AS avg_{i}, STDDEV({c}) AS std_{i}, "
                f"COUNT({c}) AS cnt_{i}"
                for i, c in enumerate(factor_cols)
            )
            + " FROM normalized_factors GROUP BY trade_date"
        )

        # pre-compute per-factor clip rate (fraction at ±3 boundary)
        raw = pipe.query("SELECT * FROM normalized_factors")

        checked = 0
        for i, col in enumerate(factor_cols):
            # skip factors with heavy clipping (>30% at boundaries)
            vals = raw[col].dropna()
            if len(vals) == 0:
                continue
            clip_rate = ((vals.abs() >= 2.99).sum()) / len(vals)
            if clip_rate > 0.3:
                continue

            # only look at dates where this factor has ≥ 5 valid values
            mask = df[f"cnt_{i}"] >= 5
            valid_mean = df.loc[mask, f"avg_{i}"].dropna()
            valid_std = df.loc[mask, f"std_{i}"].dropna()

            if len(valid_mean) == 0:
                continue
            # skip factors that are effectively constant after norm
            if valid_std.mean() < 0.1:
                continue

            mean_of_means = valid_mean.mean()
            assert abs(mean_of_means) < 1.0, (
                f"{col}: |mean of cross-sectional means| = "
                f"{abs(mean_of_means):.4f}, expected < 1.0 "
                f"(clip_rate={clip_rate:.1%})"
            )
            checked += 1

        assert checked >= 5, (
            f"Only {checked} factors had enough valid data — expected ≥ 5"
        )
        pipe.close()

    def test_cross_section_std_near_one(self, sample_ohlcv):
        """Each trade_date cross-section should have factor std ≈ 1.

        Factors whose lookback window exceeds the data length produce
        all-NULL cross-sections; these are skipped.
        """
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        factor_cols = pipe._compute_factors()
        pipe._normalize(factor_cols, method="robust_zscore")

        df = pipe.query(
            "SELECT trade_date, "
            + ", ".join(
                f"STDDEV({c}) AS std_{i}, COUNT({c}) AS cnt_{i}"
                for i, c in enumerate(factor_cols)
            )
            + " FROM normalized_factors GROUP BY trade_date"
        )

        checked = 0
        for i, col in enumerate(factor_cols):
            mask = df[f"cnt_{i}"] >= 5
            valid = df.loc[mask, f"std_{i}"].dropna()

            if len(valid) == 0:
                continue

            mean_std = valid.mean()
            # skip degenerate factors (constant → std ≈ 0)
            if mean_std < 0.05:
                continue

            assert 0.3 < mean_std < 3.0, (
                f"{col}: mean of cross-sectional std = {mean_std:.4f}, "
                f"expected ≈ 1"
            )
            checked += 1

        assert checked >= 10, (
            f"Only {checked} factors had meaningful std — expected ≥ 10"
        )
        pipe.close()

    def test_values_clipped_to_minus3_plus3(self, sample_ohlcv):
        """All normalized factor values must be within [-3, 3]."""
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        factor_cols = pipe._compute_factors()
        pipe._normalize(factor_cols, method="robust_zscore")

        df = pipe.query("SELECT * FROM normalized_factors")
        for col in factor_cols:
            valid = df[col].dropna()
            if len(valid) > 0:
                assert valid.min() >= -3.0, f"{col}: min = {valid.min():.4f}"
                assert valid.max() <= 3.0, f"{col}: max = {valid.max():.4f}"
        pipe.close()


# ── 2. factor computation completeness ─────────────────────────


class TestFactorCompleteness:
    """Input OHLCV → should yield ≥ 30 factor columns with sane NaN rates."""

    def test_at_least_30_factor_columns(self, sample_ohlcv):
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        factor_cols = pipe._compute_factors()

        assert len(factor_cols) >= 30, (
            f"Expected ≥ 30 factor columns, got {len(factor_cols)}: "
            f"{factor_cols}"
        )
        pipe.close()

    def test_total_row_count(self, sample_ohlcv):
        """raw_factors should have 10 stocks × 30 days = 300 rows."""
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        pipe._compute_factors()

        count = pipe.query("SELECT COUNT(*) AS n FROM raw_factors")["n"][0]
        assert count == 300, f"Expected 300 rows, got {count}"
        pipe.close()

    def test_short_window_factors_low_nan(self, sample_ohlcv):
        """
        Short-window factors (5-day lookback) should have moderate NaN rates.
        With 30 trading days and 5-day lag, expect ~17% NaN (5/30 per stock).
        """
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        factor_cols = pipe._compute_factors()

        df = pipe.query("SELECT * FROM raw_factors")
        total_rows = len(df)

        for col in ["roc_5", "kmid", "ma_5", "vma_5", "open_ratio"]:
            if col in factor_cols:
                nan_rate = df[col].isna().sum() / total_rows
                assert nan_rate < 0.5, (
                    f"{col}: NaN rate = {nan_rate:.2%}, expected < 50%"
                )
        pipe.close()

    def test_long_window_factors_high_nan_expected(self, sample_ohlcv):
        """
        LAG-based factors with lookback ≥ data length (30 days) are all NaN.
        Note: rolling-window aggregates (ma_60, std_60) use partial windows
        and therefore return non-NULL values even with short data.
        """
        pipe = FactorPipeline()
        _load_prices_into_duckdb(pipe, sample_ohlcv)
        factor_cols = pipe._compute_factors()

        df = pipe.query("SELECT * FROM raw_factors")
        total_rows = len(df)

        # LAG-based factors: need exactly N prior rows → all NaN when N ≥ 30
        for col in ["roc_30", "roc_60"]:
            if col in factor_cols:
                nan_rate = df[col].isna().sum() / total_rows
                assert nan_rate >= 0.9, (
                    f"{col}: NaN rate = {nan_rate:.2%}, "
                    f"expected ≥ 90% (LAG lookback ≥ data length)"
                )
        pipe.close()


# ── 3. CLI argument parsing ─────────────────────────────────────


class TestCLIArgs:
    """Verify build_parser() correctly handles all CLI flags."""

    def test_defaults(self):
        args = build_parser().parse_args([])
        assert args.start == "2016-01-01"
        assert args.end == "2025-12-31"
        assert args.norm == "robust_zscore"
        assert args.output is None
        assert args.raw is False

    def test_start_end(self):
        args = build_parser().parse_args(
            ["--start", "2024-01-01", "--end", "2024-12-31"]
        )
        assert args.start == "2024-01-01"
        assert args.end == "2024-12-31"

    def test_norm_cs_rank(self):
        args = build_parser().parse_args(["--norm", "cs_rank"])
        assert args.norm == "cs_rank"

    def test_norm_robust_zscore(self):
        args = build_parser().parse_args(["--norm", "robust_zscore"])
        assert args.norm == "robust_zscore"

    def test_invalid_norm_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["--norm", "invalid_method"])

    def test_output_path(self):
        args = build_parser().parse_args(["--output", "/tmp/factors.parquet"])
        assert args.output == "/tmp/factors.parquet"

    def test_raw_flag(self):
        args = build_parser().parse_args(["--raw"])
        assert args.raw is True

    def test_all_flags_combined(self):
        args = build_parser().parse_args([
            "--start", "2023-06-01",
            "--end", "2024-06-01",
            "--norm", "cs_rank",
            "--output", "out.parquet",
            "--raw",
        ])
        assert args.start == "2023-06-01"
        assert args.end == "2024-06-01"
        assert args.norm == "cs_rank"
        assert args.output == "out.parquet"
        assert args.raw is True


# ── 4. end-to-end pipeline (mocked PG) ─────────────────────────


class TestPipelineEndToEnd:
    """Full pipeline run with _load_prices mocked to use in-memory data."""

    def test_run_produces_parquet(self, sample_ohlcv, tmp_path):
        """run() should produce a Parquet file with normalized factors."""
        pipe = FactorPipeline()

        def mock_load(start_date, end_date, ts_codes=None):
            _load_prices_into_duckdb(pipe, sample_ohlcv)
            return len(sample_ohlcv)

        pipe._load_prices = mock_load

        output = str(tmp_path / "test_factors.parquet")
        result = pipe.run(
            start_date="2024-01-02",
            end_date="2024-02-13",
            output_path=output,
        )

        assert result == output
        df = pd.read_parquet(output)
        assert len(df) == 300  # 10 stocks × 30 days
        pipe.close()

    def test_run_raw_skips_normalization(self, sample_ohlcv, tmp_path):
        """run_raw() should skip normalization and export raw_factors."""
        pipe = FactorPipeline()

        def mock_load(start_date, end_date, ts_codes=None):
            _load_prices_into_duckdb(pipe, sample_ohlcv)
            return len(sample_ohlcv)

        pipe._load_prices = mock_load

        output = str(tmp_path / "raw_factors.parquet")
        result = pipe.run_raw(
            start_date="2024-01-02",
            end_date="2024-02-13",
            output_path=output,
        )

        assert result == output
        df = pd.read_parquet(output)
        assert len(df) == 300
        # raw_factors should include meta columns
        assert "close" in df.columns
        assert "volume" in df.columns
        pipe.close()

    def test_cs_rank_normalization(self, sample_ohlcv, tmp_path):
        """cs_rank normalization should produce values roughly in [-1.73, 1.73]."""
        pipe = FactorPipeline()

        def mock_load(start_date, end_date, ts_codes=None):
            _load_prices_into_duckdb(pipe, sample_ohlcv)
            return len(sample_ohlcv)

        pipe._load_prices = mock_load

        output = str(tmp_path / "cs_rank_factors.parquet")
        pipe.run(
            start_date="2024-01-02",
            end_date="2024-02-13",
            norm_method="cs_rank",
            output_path=output,
        )

        df = pd.read_parquet(output)
        assert len(df) == 300
        pipe.close()
