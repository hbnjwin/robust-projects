"""
ReplayEngineV5 向后兼容回归测试套件

验证项:
  1. V4 → V5 净值曲线兼容性（30 天 MA 交叉信号，容忍执行引擎差异）
  2. MasterPortfolio 回撤控制（drawdown 触及阈值时仓位强制降低）
  3. RegimeDetectorV2 CRISIS 模式下开仓限制

运行:
  pytest testing/test_v5_compat_regression.py -v
  pytest testing/test_v5_compat_regression.py -m "not slow"   # 跳过慢测试
"""
import sys
import pytest
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from live.replay_engine_v4 import ReplayEngineV4
from live.replay_engine_v5 import ReplayEngineV5
from live.master_portfolio import MasterPortfolio
from live.strategy_account import StrategyAccount
from live.regime_detector_v2 import RegimeDetectorV2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _weekday_dates(n, start=datetime(2024, 1, 2)):
    """Generate *n* weekday (Mon-Fri) date strings starting from *start*."""
    dates, d = [], start
    while len(dates) < n:
        if d.weekday() < 5:
            dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return dates


def _build_market(dates, stock_series):
    """
    Build ``market_data`` dict from date list and per-stock price arrays.

    Parameters
    ----------
    stock_series : dict[str, array-like]
        {code: [close_day0, close_day1, ...]}  one entry per date.
    """
    md = {}
    for i, dt in enumerate(dates):
        day = {}
        for code, closes in stock_series.items():
            c = round(float(closes[i]), 2)
            pc = round(float(closes[i - 1]), 2) if i > 0 else c
            day[code] = {"close": c, "volume": 10_000_000, "prev_close": pc}
        md[dt] = day
    return md


def _factor_scores(dates, codes, seed=42):
    """Deterministic factor scores for FactorStrategy."""
    rng = np.random.RandomState(seed)
    return {
        dt: {c: round(float(rng.uniform(0.3, 1.0)), 3) for c in codes}
        for dt in dates
    }


def _portfolio_with_positions(price=10.0, shares_per_account=40_000):
    """
    Create a MasterPortfolio (1 M capital, two accounts) with positions.

    Each account: 500 K capital, buys *shares_per_account* shares at *price*.
    Remaining cash per account = 500_000 - shares_per_account * price.
    """
    mp = MasterPortfolio(1_000_000)
    for name in ["Alpha", "Beta"]:
        acc = StrategyAccount(name, 500_000)
        acc.buy("000001.SZ", price, shares_per_account, date="2024-01-02")
        mp.add_strategy(name, acc)
    return mp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. V4 ↔ V5 净值曲线兼容性
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


CODES = ["000001.SZ", "000002.SZ", "000003.SZ"]

# Shared engine parameters (use V4 defaults for a fair comparison)
_SHARED_ENGINE_PARAMS = dict(
    initial_capital=1_000_000,
    trend_ratio=0.35,
    lowvol_ratio=0.20,
    factor_ratio=0.25,
    cash_ratio=0.20,
    factor_top_n=3,
    factor_rebalance_days=5,
)


@pytest.fixture(scope="module")
def ma_cross_curves():
    """
    Run V4 and V5 on identical 30-day MA-cross mock data.
    Returns (curve_v4, curve_v5).

    Price design:
      - 000001.SZ: V-shape (10 → 9.5 → 11.5) — golden-cross around day 20
      - 000002.SZ: flat oscillation around 15.0
      - 000003.SZ: gradual uptrend 20 → 22
    """
    n = 30
    a = np.concatenate([np.linspace(10.0, 9.5, 12),
                        np.linspace(9.5, 11.5, 18)])
    b = 15.0 + 0.3 * np.sin(np.linspace(0, 4 * np.pi, n))
    c = np.linspace(20.0, 22.0, n)

    dates = _weekday_dates(n)
    md = _build_market(dates, dict(zip(CODES, [a, b, c])))
    ml = _factor_scores(dates, CODES)

    params = dict(
        market_data=md,
        start_date=dates[0],
        end_date=dates[-1],
        ml_signals=ml,
        **_SHARED_ENGINE_PARAMS,
    )

    curve_v4 = ReplayEngineV4(**params).run()
    curve_v5 = ReplayEngineV5(**params).run()
    return curve_v4, curve_v5


@pytest.mark.slow
class TestV4V5EquityCurveCompat:
    """V4 → V5 升级后，在相同参数下净值曲线应保持一致。

    V5 使用 ExecutionEngine v3（费率买卖分离 long=0.0003/short=0.0013、
    买入参与率 10 % vs V2 的 5 %），允许微小数值差异。
    """

    def test_curves_same_length(self, ma_cross_curves):
        v4, v5 = ma_cross_curves
        assert len(v4) == len(v5), (
            f"equity_curve 天数不一致: V4={len(v4)} V5={len(v5)}")

    def test_dates_match(self, ma_cross_curves):
        v4, v5 = ma_cross_curves
        for i, (r4, r5) in enumerate(zip(v4, v5)):
            assert r4["date"] == r5["date"], (
                f"day {i}: V4={r4['date']} vs V5={r5['date']}")

    def test_final_equity_within_5pct(self, ma_cross_curves):
        """最终净值相差不超过 5%（容忍 v2/v3 执行引擎差异）。"""
        v4, v5 = ma_cross_curves
        eq4, eq5 = v4[-1]["equity"], v5[-1]["equity"]
        rel_diff = abs(eq4 - eq5) / max(eq4, 1)
        assert rel_diff < 0.05, (
            f"final equity diff {rel_diff:.2%} >= 5%: "
            f"V4={eq4:,.0f}  V5={eq5:,.0f}")

    def test_daily_equity_direction_consistent(self, ma_cross_curves):
        """净值日变动方向应大体一致（允许 ≤ 20 % 天数方向不同）。"""
        v4, v5 = ma_cross_curves
        if len(v4) < 2:
            pytest.skip("not enough data")
        mismatches = 0
        for i in range(1, len(v4)):
            d4 = v4[i]["equity"] - v4[i - 1]["equity"]
            d5 = v5[i]["equity"] - v5[i - 1]["equity"]
            # Only count as mismatch when BOTH have meaningful movement
            if d4 != 0 and d5 != 0 and (d4 > 0) != (d5 > 0):
                mismatches += 1
        max_allowed = max(1, len(v4) // 5)
        assert mismatches <= max_allowed, (
            f"direction mismatches {mismatches}/{len(v4)-1} > {max_allowed}")

    def test_max_drawdown_within_tolerance(self, ma_cross_curves):
        """最大回撤差异不超过 5 个百分点。"""
        v4, v5 = ma_cross_curves
        dd4, dd5 = v4[-1]["drawdown"], v5[-1]["drawdown"]
        assert abs(dd4 - dd5) < 0.05, (
            f"max_drawdown gap {abs(dd4-dd5):.2%}: "
            f"V4={dd4:.2%}  V5={dd5:.2%}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. MasterPortfolio 回撤控制 (drawdown_limit)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.slow
class TestMasterPortfolioDrawdownControl:
    """验证 MasterPortfolio 的回撤控制：

    - > 15 % 回撤 → 各账户持仓减半（半平仓）
    - > 25 % 回撤 → 所有持仓清空（强平）

    回归点: V4 → V5 升级曾导致 drawdown_limit 参数被忽略。
    """

    def test_no_action_below_15pct(self):
        """回撤 < 15 % 时不触发任何控制。"""
        mp = _portfolio_with_positions(price=10.0, shares_per_account=40_000)
        # Each acct: cash=100K, pos=40K*10=400K → total=500K, portfolio=1M
        # Drop to 9.0: pos=40K*9=360K → acct=460K → portfolio=920K
        # DD = (1M-920K)/1M = 8 %
        prices = {"000001.SZ": {"close": 9.0, "volume": 10_000_000,
                                "prev_close": 10.0}}
        for acc in mp.strategy_accounts.values():
            acc.mark_to_market(prices)
        mp.update_total_equity()
        mp.apply_drawdown_control(prices)

        assert not mp.drawdown_control_triggered
        for acc in mp.strategy_accounts.values():
            assert "000001.SZ" in acc.positions
            assert acc.positions["000001.SZ"]["shares"] == 40_000

    def test_half_liquidation_above_15pct(self):
        """回撤 > 15 % → 各账户持仓减半。"""
        mp = _portfolio_with_positions(price=10.0, shares_per_account=40_000)
        # Drop to 8.0: pos=40K*8=320K → acct=420K → portfolio=840K
        # DD = (1M-840K)/1M = 16 % > 15 %
        prices = {"000001.SZ": {"close": 8.0, "volume": 10_000_000,
                                "prev_close": 10.0}}
        for acc in mp.strategy_accounts.values():
            acc.mark_to_market(prices)
        mp.update_total_equity()
        mp.apply_drawdown_control(prices)

        assert mp.drawdown_control_triggered
        for acc in mp.strategy_accounts.values():
            assert acc.positions["000001.SZ"]["shares"] == 20_000, (
                "持仓应减半 (40000 → 20000)")

    def test_full_liquidation_above_25pct(self):
        """回撤 > 25 % → 所有持仓清空。"""
        mp = _portfolio_with_positions(price=10.0, shares_per_account=40_000)
        # Drop to 6.5: pos=40K*6.5=260K → acct=360K → portfolio=720K
        # DD = (1M-720K)/1M = 28 % > 25 %
        prices = {"000001.SZ": {"close": 6.5, "volume": 10_000_000,
                                "prev_close": 10.0}}
        for acc in mp.strategy_accounts.values():
            acc.mark_to_market(prices)
        mp.update_total_equity()
        mp.apply_drawdown_control(prices)

        assert mp.drawdown_control_triggered
        for acc in mp.strategy_accounts.values():
            assert len(acc.positions) == 0, "强平后应无持仓"

    def test_cash_recovered_with_fees(self):
        """强平卖出后现金正确回收（含 0.1 % 滑点 + 手续费）。"""
        mp = _portfolio_with_positions(price=10.0, shares_per_account=40_000)
        prices = {"000001.SZ": {"close": 6.5, "volume": 10_000_000,
                                "prev_close": 10.0}}
        cash_before = {n: a.cash for n, a in mp.strategy_accounts.items()}

        for acc in mp.strategy_accounts.values():
            acc.mark_to_market(prices)
        mp.update_total_equity()
        mp.apply_drawdown_control(prices, fee_rate=0.0003)

        for name, acc in mp.strategy_accounts.items():
            sell_price = 6.5 * 0.999          # slippage
            revenue = 40_000 * sell_price
            fee = revenue * 0.0003
            expected = cash_before[name] + revenue - fee
            assert abs(acc.cash - expected) < 0.01, (
                f"{name}: cash={acc.cash:.2f}  expected={expected:.2f}")

    def test_drawdown_control_in_v5_engine(self):
        """
        V5 引擎集成: 持仓标的单边暴跌触发回撤控制。

        数据设计: 股票 A 暴跌 60 %，股票 B 同步上涨 60 %，C 不动。
        市场均价恒为 10.0 → 不触发 CRISIS → 回撤控制必须独立生效。
        预加载集中持仓于 A（模拟前期建仓），当 A 暴跌时组合回撤超过
        15 % → drawdown_control 应当触发。

        回归点: V4 → V5 升级曾导致 drawdown_limit 参数被忽略。
        """
        n = 50
        dates = _weekday_dates(n)

        # A: 15 天平稳 → 25 天跌至 4.0 (-60%) → 10 天低位
        # B: 15 天平稳 → 25 天涨至 16.0 (+60%) → 10 天高位
        # C: 全程 10.0
        # 市场均价 = (A+B+C)/3 = 10.0 恒定 → 无 CRISIS
        a = np.concatenate([np.full(15, 10.0),
                            np.linspace(10.0, 4.0, 25),
                            np.full(10, 4.0)])
        b = np.concatenate([np.full(15, 10.0),
                            np.linspace(10.0, 16.0, 25),
                            np.full(10, 16.0)])
        c = np.full(n, 10.0)

        series = {"000001.SZ": a, "000002.SZ": b, "000003.SZ": c}
        md = _build_market(dates, series)
        ml = _factor_scores(dates[15:], CODES)

        engine = ReplayEngineV5(
            market_data=md,
            start_date=dates[15],       # 前 15 天做预热
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml,
            trend_ratio=0.0,
            lowvol_ratio=0.0,
            factor_ratio=0.80,
            cash_ratio=0.20,
        )

        # 预加载集中持仓于 A（模拟前期建仓阶段的结果）
        factor_acc = engine.master.strategy_accounts["Factor"]
        buy_shares = (int(factor_acc.cash * 0.90 / 10.0) // 100) * 100
        factor_acc.buy("000001.SZ", 10.0, buy_shares, date=dates[0])

        curve = engine.run()

        assert engine.master.drawdown_control_triggered, (
            "V5 引擎未触发回撤控制 — drawdown_limit 可能被忽略（回归 bug）"
            f"  (max_drawdown={engine.master.max_drawdown:.2%})")
        assert engine.master.max_drawdown > 0.15, (
            f"max_drawdown={engine.master.max_drawdown:.2%}，预期 > 15 %")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. RegimeDetectorV2 CRISIS 模式限制开仓
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@pytest.mark.slow
class TestCrisisRegimeRestriction:
    """验证 RegimeDetectorV2 的 CRISIS 检测和引擎层面的开仓限制。"""

    # ── 单元测试：RegimeDetectorV2 ────────────────────────────

    def test_single_day_crash_triggers_crisis(self):
        """单日跌幅 >= 3 % 触发 CRISIS。"""
        rd = RegimeDetectorV2()
        for i in range(25):
            rd.update(100.0 + i * 0.2)
        assert rd.detect() != "CRISIS"

        # -4 % 单日暴跌
        last = 100.0 + 24 * 0.2            # 104.8
        rd.update(last * 0.96)
        assert rd.detect() == "CRISIS"

    def test_two_day_cumulative_triggers_crisis(self):
        """连续两日累计跌幅 >= 5 % 触发 CRISIS（单日不足 3 %）。"""
        rd = RegimeDetectorV2()
        for i in range(25):
            rd.update(100.0 + i * 0.1)

        last = 100.0 + 24 * 0.1            # 102.4
        day1_price = last * 0.974           # -2.6 %
        rd.update(day1_price)
        assert rd.detect() != "CRISIS", (
            "单日 -2.6 % 不应独立触发 CRISIS")

        day2_price = day1_price * 0.974     # 再跌 -2.6 %，累计 ≈ -5.1 %
        rd.update(day2_price)
        assert rd.detect() == "CRISIS", (
            "两日累计 -5.1 % 应触发 CRISIS")

    def test_crisis_cooldown_persists_5_days(self):
        """CRISIS 触发后冷却期至少 5 天，期间始终返回 CRISIS。"""
        rd = RegimeDetectorV2()
        for i in range(25):
            rd.update(100.0 + i * 0.1)

        # 触发 CRISIS（-5 %）
        last = 100.0 + 24 * 0.1
        rd.update(last * 0.95)
        assert rd.detect() == "CRISIS"

        # 后续 5 天：价格平稳，CRISIS 应持续
        flat = last * 0.95
        crisis_count = 0
        for _ in range(5):
            rd.update(flat)
            if rd.detect() == "CRISIS":
                crisis_count += 1
        assert crisis_count == 5, (
            f"CRISIS 仅持续 {crisis_count}/5 天冷却期")

    def test_crisis_ends_after_cooldown(self):
        """冷却期结束且行情平稳后应退出 CRISIS。"""
        rd = RegimeDetectorV2()
        for i in range(25):
            rd.update(100.0 + i * 0.1)

        last = 100.0 + 24 * 0.1
        rd.update(last * 0.95)              # 触发
        rd.detect()                          # 消费触发

        flat = last * 0.95
        for _ in range(5):                   # 5 天冷却
            rd.update(flat)
            rd.detect()

        # 第 6 天：冷却结束
        rd.update(flat)
        assert rd.detect() != "CRISIS", (
            "5 天冷却期后行情平稳，应退出 CRISIS")

    # ── 集成测试：V5 引擎 CRISIS 行为 ────────────────────────

    def test_v5_no_new_positions_during_crisis(self):
        """
        V5 引擎集成：CRISIS 期间不应开新仓，现有持仓应被清仓信号卖出。

        数据设计:
          - 20 天预热（regime detector 积累历史）
          - 25 天交易（策略建仓）
          - 第 26 天: -6 % 暴跌 → 触发 CRISIS
          - 9 天冷却 + 恢复

        验证:
          a) 暴跌前有买入交易（策略确实在建仓）
          b) CRISIS 冷却期内无任何买入交易
          c) 暴跌数据确实能触发 RegimeDetectorV2 的 CRISIS
        """
        n_total = 55                         # 20 warmup + 35 trading
        warmup_end = 20
        crash_idx = 45                       # absolute index (trading day 25)

        dates = _weekday_dates(n_total)
        crash_date = dates[crash_idx]

        # 平稳上涨 → 暴跌 → 低位盘整
        pre_crash  = np.linspace(10.0, 11.0, crash_idx)
        crash_val  = 11.0 * 0.94             # -6 %
        post_crash = np.full(n_total - crash_idx, crash_val)
        base = np.concatenate([pre_crash, post_crash])

        series = {c: base * (1 + 0.05 * i) for i, c in enumerate(CODES)}
        md = _build_market(dates, series)
        ml = _factor_scores(dates[warmup_end:], CODES)

        engine = ReplayEngineV5(
            market_data=md,
            start_date=dates[warmup_end],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml,
        )
        curve = engine.run()

        # (a) 暴跌前应有买入交易（测试前提）
        buys_before = [
            t for acc in engine.master.strategy_accounts.values()
            for t in acc.trade_log
            if t["action"] == "buy" and t["date"] < crash_date
        ]
        assert len(buys_before) > 0, (
            "暴跌前无买入交易，测试前提不成立（策略未建仓）")

        # (b) CRISIS 冷却期内（crash day + 5 天）不应有买入交易
        cooldown_end_idx = min(crash_idx + 6, n_total)
        cooldown_dates = set(dates[crash_idx:cooldown_end_idx])

        buys_during_crisis = [
            t for acc in engine.master.strategy_accounts.values()
            for t in acc.trade_log
            if t["action"] == "buy" and t["date"] in cooldown_dates
        ]
        assert len(buys_during_crisis) == 0, (
            f"CRISIS 期间发现 {len(buys_during_crisis)} 笔买入: "
            f"{[(t['date'], t['code']) for t in buys_during_crisis]}")

        # (c) 独立验证: 暴跌数据触发 CRISIS
        rd = RegimeDetectorV2()
        for dt in dates[:crash_idx]:
            closes = [md[dt][c]["close"] for c in CODES]
            rd.update(np.mean(closes))
        crash_closes = [md[crash_date][c]["close"] for c in CODES]
        rd.update(np.mean(crash_closes))
        assert rd.detect() == "CRISIS", (
            "-6 % 暴跌应触发 CRISIS（独立验证失败）")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Direct execution support
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
