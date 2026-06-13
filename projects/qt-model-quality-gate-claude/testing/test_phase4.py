"""
Phase 4 集成测试
验证因子库: ts_factors / cs_factors / ic_analysis
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def make_price_series(n=100, seed=42):
    np.random.seed(seed)
    prices = 10.0 * np.cumprod(1 + np.random.normal(0.0005, 0.015, n))
    return pd.Series(prices, name="close")


def test_ts_factors():
    print("\n[T1] 时序因子函数库")
    from factor_lib.ts_factors import (
        ts_delay, ts_delta, ts_pct, ts_mean, ts_std,
        ts_min, ts_max, ts_rank, ts_argmax, ts_corr,
        ts_slope, ts_rsquare, ts_zscore,
        factor_rsi, factor_macd_diff, factor_boll_pos, factor_atr,
    )

    close = make_price_series(100)
    high  = close * 1.01
    low   = close * 0.99

    # 基础算子
    assert ts_delay(close, 5).iloc[5] == close.iloc[0]
    assert abs(ts_delta(close, 1).iloc[1] - (close.iloc[1] - close.iloc[0])) < 1e-9
    assert ts_mean(close, 5).notna().sum() == 100
    assert ts_std(close, 20).iloc[:19].isna().sum() <= 1  # min_periods=2
    assert (ts_min(close, 10) <= close).all()
    assert (ts_max(close, 10) >= close).all()
    print("  基础算子 ✓")

    # ts_rank 范围 [0,1]
    rank = ts_rank(close, 20)
    assert rank.dropna().between(0, 1).all()
    print("  ts_rank 范围 [0,1] ✓")

    # ts_slope / ts_rsquare
    slope = ts_slope(close, 20)
    r2    = ts_rsquare(close, 20)
    assert slope.dropna().shape[0] > 0
    assert r2.dropna().between(0, 1).all()
    print("  ts_slope / ts_rsquare ✓")

    # 技术指标
    rsi = factor_rsi(close, 14)
    assert rsi.dropna().between(0, 100).all()
    print(f"  RSI 范围 [0,100] ✓  (mean={rsi.mean():.1f})")

    macd = factor_macd_diff(close)
    assert macd.notna().sum() > 0
    print("  MACD DIF ✓")

    boll = factor_boll_pos(close, 20)
    assert boll.dropna().shape[0] > 0
    print("  布林带位置 ✓")

    atr = factor_atr(high, low, close, 14)
    assert (atr.dropna() > 0).all()
    print("  ATR > 0 ✓")

    print("[T1] PASS")


def test_cs_factors():
    print("\n[T2] 截面因子函数库")
    from factor_lib.cs_factors import (
        cs_rank, cs_zscore, cs_robust_zscore,
        cs_winsorize, cs_neutralize, cs_scale, cs_demean,
        cs_top_n, cs_bottom_n,
    )

    np.random.seed(0)
    s = pd.Series(np.random.randn(50), index=[f"{i:06d}.SZ" for i in range(50)])

    # cs_rank
    r = cs_rank(s)
    assert r.between(0, 1).all()
    print("  cs_rank [0,1] ✓")

    # cs_zscore
    z = cs_zscore(s)
    assert abs(z.mean()) < 1e-9
    assert abs(z.std() - 1.0) < 0.01
    print("  cs_zscore mean≈0, std≈1 ✓")

    # cs_robust_zscore
    rz = cs_robust_zscore(s)
    assert rz.between(-3, 3).all()
    print("  cs_robust_zscore clip[-3,3] ✓")

    # cs_winsorize
    w = cs_winsorize(s, q=0.05)
    assert w.min() >= s.quantile(0.05) - 1e-9
    assert w.max() <= s.quantile(0.95) + 1e-9
    print("  cs_winsorize ✓")

    # cs_neutralize
    groups = pd.Series(["A"] * 25 + ["B"] * 25, index=s.index)
    n = cs_neutralize(s, groups)
    assert abs(n[groups == "A"].mean()) < 1e-9
    assert abs(n[groups == "B"].mean()) < 1e-9
    print("  cs_neutralize 行业均值≈0 ✓")

    # cs_scale
    sc = cs_scale(s)
    assert abs(sc.abs().sum() - 1.0) < 1e-9
    print("  cs_scale 绝对值之和=1 ✓")

    # cs_top_n / cs_bottom_n
    top5 = cs_top_n(s, 5)
    assert top5.sum() == 5
    bot5 = cs_bottom_n(s, 5)
    assert bot5.sum() == 5
    print("  cs_top_n / cs_bottom_n ✓")

    print("[T2] PASS")


def test_ic_analysis():
    print("\n[T3] IC 分析工具")
    from factor_lib.ic_analysis import ICAnalyzer, factor_quantile_return

    np.random.seed(42)
    n_dates  = 60
    n_stocks = 30
    dates    = pd.date_range("2024-01-01", periods=n_dates, freq="B")
    stocks   = [f"{i:06d}.SZ" for i in range(n_stocks)]

    # 构造有信号的因子（与未来收益正相关）
    true_signal = np.random.randn(n_dates, n_stocks)
    noise       = np.random.randn(n_dates, n_stocks) * 2
    factor_df   = pd.DataFrame(true_signal, index=dates, columns=stocks)
    return_df   = pd.DataFrame(true_signal * 0.3 + noise, index=dates, columns=stocks)

    analyzer = ICAnalyzer(factor_df, return_df)
    ic_series = analyzer.daily_ic()
    assert len(ic_series) > 0
    print(f"  IC 序列长度: {len(ic_series)} 天 ✓")

    summary = analyzer.run(verbose=False)
    assert "IC_mean" in summary
    assert "ICIR" in summary
    # 有信号的因子 IC 均值应 > 0
    assert summary["IC_mean"] > 0, f"IC_mean={summary['IC_mean']} 应>0"
    print(f"  IC_mean={summary['IC_mean']:+.4f}  ICIR={summary['ICIR']:+.4f} ✓")

    # 分位数收益
    qret = factor_quantile_return(factor_df, return_df, n_quantiles=5)
    assert not qret.empty
    assert "Q1" in qret.columns and "Q5" in qret.columns
    q1_mean = qret["Q1"].mean()
    q5_mean = qret["Q5"].mean()
    print(f"  分位数收益: Q1={q1_mean:+.4f}  Q5={q5_mean:+.4f} ✓")

    print("[T3] PASS")


def test_alpha_factors():
    print("\n[T4] Alpha 精选因子")
    from factor_lib.ts_factors import alpha_001, alpha_006, alpha_013, alpha_016, alpha_028

    np.random.seed(1)
    n = 100
    close  = make_price_series(n)
    open_  = close * (1 + np.random.normal(0, 0.005, n))
    high   = close * (1 + abs(np.random.normal(0, 0.01, n)))
    low    = close * (1 - abs(np.random.normal(0, 0.01, n)))
    volume = pd.Series(np.random.uniform(1e6, 1e7, n))
    returns = close.pct_change()

    a1 = alpha_001(returns, close)
    assert a1.dropna().shape[0] > 0
    print(f"  alpha_001: {a1.dropna().shape[0]} 有效值 ✓")

    a6 = alpha_006(open_, volume)
    assert a6.dropna().shape[0] > 0
    print(f"  alpha_006: {a6.dropna().shape[0]} 有效值 ✓")

    a13 = alpha_013(close, volume)
    assert a13.dropna().shape[0] > 0
    print(f"  alpha_013: {a13.dropna().shape[0]} 有效值 ✓")

    a16 = alpha_016(high, volume)
    assert a16.dropna().shape[0] > 0
    print(f"  alpha_016: {a16.dropna().shape[0]} 有效值 ✓")

    a28 = alpha_028(close, high, low, volume)
    assert a28.dropna().shape[0] > 0
    print(f"  alpha_028: {a28.dropna().shape[0]} 有效值 ✓")

    print("[T4] PASS")


def test_factor_lib_import():
    print("\n[T5] factor_lib 统一导入")
    import factor_lib
    assert hasattr(factor_lib, "ts_mean")
    assert hasattr(factor_lib, "cs_rank")
    assert hasattr(factor_lib, "ICAnalyzer")
    print("  factor_lib 导入完整 ✓")
    print("[T5] PASS")


if __name__ == "__main__":
    try:
        test_ts_factors()
        test_cs_factors()
        test_ic_analysis()
        test_alpha_factors()
        test_factor_lib_import()
        print("\n" + "="*50)
        print("  Phase 4 ALL TESTS PASSED ✓")
        print("="*50)
    except Exception as e:
        import traceback
        print(f"\n[FAIL] {e}")
        traceback.print_exc()
        sys.exit(1)
