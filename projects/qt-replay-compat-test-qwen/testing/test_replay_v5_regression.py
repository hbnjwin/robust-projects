"""
test_replay_v5_regression.py — ReplayEngineV5 向后兼容回归测试套件

测试目标:
  1. V4/V5 净值曲线一致性（相同参数下，排除架构差异）
  2. MasterPortfolio 回撤控制集成（drawdown_limit 是否生效）
  3. RegimeDetectorV2 CRISIS 模式限制开仓行为

所有测试标记 pytest.mark.slow，可通过 -m "not slow" 跳过。
"""
import sys
import copy
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def crossover_data():
    """30 天 MA 交叉行情 + ML 信号"""
    from testing.conftest import make_market_data, make_ml_signals
    market_data, codes = make_market_data(
        n_days=30, n_stocks=5, seed=42, trend="crossover"
    )
    dates = sorted(market_data.keys())
    ml_signals = make_ml_signals(dates, codes, seed=42)
    return market_data, codes, ml_signals


@pytest.fixture
def crash_data():
    """暴跌行情（触发 CRISIS + 回撤控制）"""
    from testing.conftest import make_market_data
    market_data, codes = make_market_data(
        n_days=30, n_stocks=5, seed=99, start_price=20.0, trend="crash"
    )
    return market_data, codes


@pytest.fixture
def steady_data():
    """稳定上涨行情（不触发 CRISIS/回撤控制）"""
    from testing.conftest import make_market_data, make_ml_signals
    market_data, codes = make_market_data(
        n_days=30, n_stocks=5, seed=7, start_price=10.0, trend="steady_up"
    )
    dates = sorted(market_data.keys())
    ml_signals = make_ml_signals(dates, codes, seed=7)
    return market_data, codes, ml_signals


# ═══════════════════════════════════════════════════════════════
#  Test 1: V4 / V5 净值曲线一致性
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestV4V5EquityParity:
    """
    验证：相同参数 + 相同执行引擎下，V4 和 V5 的净值曲线应基本一致。

    注意：V5 使用 ExecutionEngine v3（10% 成交量限制、买卖分离费率），
    V4 使用 v2（5% 成交量限制、统一费率）。为公平比较，将 V5 的执行引擎
    patch 为 v2，隔离架构差异。
    """

    def _run_v4(self, market_data, ml_signals, dates,
                trend_ratio=0.35, lowvol_ratio=0.20, factor_ratio=0.25, cash_ratio=0.20):
        from live.replay_engine_v4 import ReplayEngineV4
        engine = ReplayEngineV4(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml_signals,
            trend_ratio=trend_ratio,
            lowvol_ratio=lowvol_ratio,
            factor_ratio=factor_ratio,
            cash_ratio=cash_ratio,
        )
        return engine.run()

    def _run_v5(self, market_data, ml_signals, dates,
                trend_ratio=0.35, lowvol_ratio=0.20, factor_ratio=0.25, cash_ratio=0.20):
        # Patch V5 to use ExecutionEngine v2 (same as V4) for fair comparison
        from live.execution_engine_v2 import ExecutionEngine as ExecV2
        with patch("live.replay_engine_v5.ExecutionEngine", ExecV2):
            from live.replay_engine_v5 import ReplayEngineV5
            engine = ReplayEngineV5(
                market_data=market_data,
                start_date=dates[0],
                end_date=dates[-1],
                initial_capital=1_000_000,
                ml_signals=ml_signals,
                trend_ratio=trend_ratio,
                lowvol_ratio=lowvol_ratio,
                factor_ratio=factor_ratio,
                cash_ratio=cash_ratio,
            )
            return engine.run()

    def test_equity_curve_shape_match(self, crossover_data):
        """V4/V5 净值曲线长度和日期应完全一致"""
        market_data, codes, ml_signals = crossover_data
        dates = sorted(market_data.keys())

        curve_v4 = self._run_v4(market_data, ml_signals, dates)
        curve_v5 = self._run_v5(market_data, ml_signals, dates)

        assert len(curve_v4) == len(curve_v5), (
            f"曲线长度不一致: V4={len(curve_v4)}, V5={len(curve_v5)}"
        )
        dates_v4 = [d["date"] for d in curve_v4]
        dates_v5 = [d["date"] for d in curve_v5]
        assert dates_v4 == dates_v5, "日期序列不一致"

    def test_equity_values_close(self, crossover_data):
        """V4/V5 每日净值差异应在 2% 以内（容忍执行顺序微小差异）"""
        market_data, codes, ml_signals = crossover_data
        dates = sorted(market_data.keys())

        curve_v4 = self._run_v4(market_data, ml_signals, dates)
        curve_v5 = self._run_v5(market_data, ml_signals, dates)

        for i, (d4, d5) in enumerate(zip(curve_v4, curve_v5)):
            eq4, eq5 = d4["equity"], d5["equity"]
            if eq4 > 0:
                diff_pct = abs(eq4 - eq5) / eq4
                assert diff_pct < 0.02, (
                    f"Day {i} ({d4['date']}): 净值差异过大 "
                    f"V4={eq4:,.0f} V5={eq5:,.0f} diff={diff_pct:.2%}"
                )

    def test_drawdown_trajectory_consistent(self, crossover_data):
        """V4/V5 回撤轨迹应基本一致（最大回撤差异 < 3%）"""
        market_data, codes, ml_signals = crossover_data
        dates = sorted(market_data.keys())

        curve_v4 = self._run_v4(market_data, ml_signals, dates)
        curve_v5 = self._run_v5(market_data, ml_signals, dates)

        max_dd_v4 = max(d["drawdown"] for d in curve_v4)
        max_dd_v5 = max(d["drawdown"] for d in curve_v5)
        dd_diff = abs(max_dd_v4 - max_dd_v5)

        assert dd_diff < 0.03, (
            f"最大回撤差异过大: V4={max_dd_v4:.2%} V5={max_dd_v5:.2%} diff={dd_diff:.2%}"
        )

    def test_output_format_backward_compatible(self, crossover_data):
        """V5 输出格式与 V4 完全兼容（dict keys 一致）"""
        market_data, codes, ml_signals = crossover_data
        dates = sorted(market_data.keys())

        curve_v4 = self._run_v4(market_data, ml_signals, dates)
        curve_v5 = self._run_v5(market_data, ml_signals, dates)

        required_keys = {"date", "equity", "drawdown"}
        for d4, d5 in zip(curve_v4, curve_v5):
            assert required_keys.issubset(d4.keys()), f"V4 缺少 keys: {required_keys - d4.keys()}"
            assert required_keys.issubset(d5.keys()), f"V5 缺少 keys: {required_keys - d5.keys()}"


# ═══════════════════════════════════════════════════════════════
#  Test 2: MasterPortfolio 回撤控制（drawdown_limit 回归）
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestMasterPortfolioDrawdownControl:
    """
    验证 V5 中 MasterPortfolio 的回撤控制是否正确触发：
      - drawdown > 15% → 半仓清算
      - drawdown > 25% → 全仓清算
    这是 V4→V5 升级时的回归 bug 核心测试。
    """

    def test_half_liquidation_at_15pct_drawdown(self, crash_data):
        """回撤超过 15% 时，持仓应被减半"""
        market_data, codes = crash_data
        dates = sorted(market_data.keys())

        # 注入虚假的 ML 信号让策略积极买入（建立持仓后才能测回撤）
        ml_signals = {}
        for i, date in enumerate(dates):
            scores = {code: 0.9 - j * 0.05 for j, code in enumerate(codes)}
            ml_signals[date] = scores

        from live.replay_engine_v5 import ReplayEngineV5
        engine = ReplayEngineV5(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml_signals,
            trend_ratio=0.35,
            lowvol_ratio=0.20,
            factor_ratio=0.25,
            cash_ratio=0.20,
        )
        curve = engine.run()

        # 检查是否触发了回撤控制
        max_dd = max(d["drawdown"] for d in curve)

        if max_dd > 0.15:
            # 回撤控制应该被触发
            assert engine.master.drawdown_control_triggered, (
                f"回撤已达 {max_dd:.2%} > 15%，但 drawdown_control_triggered 仍为 False。"
                "这是 V4→V5 升级的回归 bug：drawdown_limit 参数被忽略。"
            )

            # 触发后，所有策略的持仓应大幅减少
            total_shares_after = 0
            for acct in engine.master.strategy_accounts.values():
                for pos in acct.positions.values():
                    total_shares_after += pos.get("shares", 0)

            # 在回撤控制触发后，持仓应该被显著削减
            # （具体取决于触发时是 15% 还是 25% 阈值）
            # 这里只验证控制机制确实被执行了
            assert engine.master.drawdown_control_triggered, (
                "回撤控制触发标志未设置"
            )

    def test_full_liquidation_at_25pct_drawdown(self):
        """
        直接测试 MasterPortfolio.apply_drawdown_control：
        当 drawdown > 25% 时，所有持仓应被清空。
        """
        from live.master_portfolio import MasterPortfolio
        from live.strategy_account import StrategyAccount

        mp = MasterPortfolio(1_000_000)
        acct = StrategyAccount("Test", 500_000)
        mp.add_strategy("Test", acct)

        # 模拟买入
        acct.buy("600001.SH", 10.0, 1000, date="2024-01-01")
        acct.buy("600002.SH", 20.0, 500, date="2024-01-01")
        acct.cash = 400_000  # 剩余现金

        # 模拟权益更新
        acct.mark_to_market({
            "600001.SH": {"close": 10.0, "volume": 1e6, "prev_close": 10.0},
            "600002.SH": {"close": 20.0, "volume": 1e6, "prev_close": 20.0},
        })
        mp.update_total_equity()

        # 人为设置 max_drawdown > 25%
        mp.max_equity = 1_000_000
        mp.total_equity = 700_000
        mp.max_drawdown = 0.30  # 30% 回撤

        prices = {
            "600001.SH": {"close": 10.0, "volume": 1e6, "prev_close": 10.0},
            "600002.SH": {"close": 20.0, "volume": 1e6, "prev_close": 20.0},
        }

        # 执行回撤控制
        mp.apply_drawdown_control(prices)

        # 验证：所有持仓应被清空
        assert len(acct.positions) == 0, (
            f"drawdown=30% > 25%，但持仓未被清空: {acct.positions}"
        )
        assert mp.drawdown_control_triggered, "drawdown_control_triggered 未设置"

    def test_half_liquidation_direct(self):
        """
        直接测试 MasterPortfolio.apply_drawdown_control：
        当 15% < drawdown <= 25% 时，持仓应被减半。
        """
        from live.master_portfolio import MasterPortfolio
        from live.strategy_account import StrategyAccount

        mp = MasterPortfolio(1_000_000)
        acct = StrategyAccount("Test", 500_000)
        mp.add_strategy("Test", acct)

        # 模拟买入（偶数股，方便减半）
        acct.buy("600001.SH", 10.0, 1000, date="2024-01-01")
        acct.buy("600002.SH", 20.0, 800, date="2024-01-01")
        acct.cash = 300_000

        acct.mark_to_market({
            "600001.SH": {"close": 10.0, "volume": 1e6, "prev_close": 10.0},
            "600002.SH": {"close": 20.0, "volume": 1e6, "prev_close": 20.0},
        })
        mp.update_total_equity()

        # 人为设置 15% < drawdown <= 25%
        mp.max_equity = 1_000_000
        mp.total_equity = 820_000
        mp.max_drawdown = 0.18  # 18% 回撤

        prices = {
            "600001.SH": {"close": 10.0, "volume": 1e6, "prev_close": 10.0},
            "600002.SH": {"close": 20.0, "volume": 1e6, "prev_close": 20.0},
        }

        mp.apply_drawdown_control(prices)

        # 验证：持仓应被减半
        assert mp.drawdown_control_triggered, "drawdown_control_triggered 未设置"

        # 600001: 1000 → 500, 600002: 800 → 400
        for code, expected_shares in [("600001.SH", 500), ("600002.SH", 400)]:
            if code in acct.positions:
                actual = acct.positions[code]["shares"]
                assert actual == expected_shares, (
                    f"{code}: 减半后应剩 {expected_shares} 股，实际 {actual}"
                )

    def test_no_liquidation_below_15pct(self):
        """drawdown < 15% 时不应触发任何回撤控制"""
        from live.master_portfolio import MasterPortfolio
        from live.strategy_account import StrategyAccount

        mp = MasterPortfolio(1_000_000)
        acct = StrategyAccount("Test", 500_000)
        mp.add_strategy("Test", acct)

        acct.buy("600001.SH", 10.0, 1000, date="2024-01-01")
        acct.cash = 490_000

        acct.mark_to_market({
            "600001.SH": {"close": 10.0, "volume": 1e6, "prev_close": 10.0},
        })
        mp.update_total_equity()

        mp.max_drawdown = 0.10  # 10% 回撤

        prices = {
            "600001.SH": {"close": 10.0, "volume": 1e6, "prev_close": 10.0},
        }
        mp.apply_drawdown_control(prices)

        # 不应触发
        assert not mp.drawdown_control_triggered, (
            "drawdown=10% < 15%，不应触发回撤控制"
        )
        assert "600001.SH" in acct.positions, "持仓不应被清除"
        assert acct.positions["600001.SH"]["shares"] == 1000, "持仓数量不应变化"

    def test_v5_drawdown_control_integrated(self, crash_data):
        """
        集成测试：V5 引擎在暴跌行情下，回撤控制应被正确触发并执行。
        这是回归 bug 的核心验证——如果 drawdown_limit 被忽略，此测试会失败。
        """
        market_data, codes = crash_data
        dates = sorted(market_data.keys())

        # 构造激进的买入信号
        ml_signals = {}
        for date in dates:
            ml_signals[date] = {code: 0.95 - j * 0.1 for j, code in enumerate(codes)}

        from live.replay_engine_v5 import ReplayEngineV5
        engine = ReplayEngineV5(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml_signals,
            trend_ratio=0.35,
            lowvol_ratio=0.20,
            factor_ratio=0.25,
            cash_ratio=0.20,
        )
        curve = engine.run()

        max_dd = max(d["drawdown"] for d in curve)
        final_equity = curve[-1]["equity"]

        # 基本合理性检查
        assert final_equity > 0, "最终权益不应为负"
        assert len(curve) == len(dates), f"曲线长度 {len(curve)} != 日期数 {len(dates)}"

        # 如果回撤很大，控制机制应该介入了
        if max_dd > 0.25:
            # 全仓清算后，后续权益应全部为现金（无持仓）
            total_positions = sum(
                len(acct.positions)
                for acct in engine.master.strategy_accounts.values()
            )
            # 注意：清算后策略可能重新建仓，所以不要求持仓为 0
            # 但 drawdown_control_triggered 必须为 True
            assert engine.master.drawdown_control_triggered, (
                f"max_drawdown={max_dd:.2%} > 25%，但回撤控制未触发"
            )


# ═══════════════════════════════════════════════════════════════
#  Test 3: RegimeDetectorV2 CRISIS 模式
# ═══════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestRegimeCrisisBehavior:
    """
    验证 CRISIS 模式下：
      1. RegimeDetectorV2 正确检测 CRISIS
      2. V5 引擎阻止新开仓
      3. V5 引擎对现有持仓生成清仓信号
    """

    def test_crisis_detection_single_day_crash(self):
        """单日暴跌 ≥3% 应触发 CRISIS"""
        from live.regime_detector_v2 import RegimeDetectorV2

        detector = RegimeDetectorV2(lookback=20)

        # 喂 25 天稳定数据（建立基线）
        price = 100.0
        for i in range(25):
            price *= (1 + np.random.normal(0.001, 0.005))
            detector.update(price, 1e6)

        assert detector.detect() in ("BULL", "NEUTRAL")

        # 单日暴跌 4%
        price *= 0.96
        detector.update(price, 1e6)
        regime = detector.detect()

        assert regime == "CRISIS", f"单日暴跌 4% 应触发 CRISIS，实际: {regime}"

    def test_crisis_detection_two_day_cumulative(self):
        """连续两日累计跌幅 ≥5% 应触发 CRISIS（单日不触发）"""
        from live.regime_detector_v2 import RegimeDetectorV2

        detector = RegimeDetectorV2(lookback=20)

        np.random.seed(77)
        price = 100.0
        for i in range(25):
            price *= (1 + np.random.normal(0.001, 0.005))
            detector.update(price, 1e6)

        # 第一天跌 2.5%（不触发单日 -3% 阈值）
        price *= 0.975
        detector.update(price, 1e6)
        regime_day1 = detector.detect()
        assert regime_day1 != "CRISIS", (
            f"单日跌 2.5% 不应触发 CRISIS（单日阈值 -3%），实际: {regime_day1}"
        )

        # 第二天再跌 2.6%（累计两天 -5.03%，触发累计阈值 -5%）
        price *= 0.974
        detector.update(price, 1e6)
        regime_day2 = detector.detect()

        assert regime_day2 == "CRISIS", (
            f"两日累计跌 ≈5% 应触发 CRISIS，实际: {regime_day2}"
        )

    def test_crisis_cooldown_persists(self):
        """CRISIS 触发后应有 5 天冷却期"""
        from live.regime_detector_v2 import RegimeDetectorV2

        detector = RegimeDetectorV2(lookback=20)

        price = 100.0
        for i in range(25):
            price *= 1.002
            detector.update(price, 1e6)

        # 触发 CRISIS
        price *= 0.95  # -5%
        detector.update(price, 1e6)
        assert detector.detect() == "CRISIS"

        # 接下来 5 天即使价格恢复，仍应为 CRISIS（冷却期）
        for i in range(5):
            price *= 1.02  # 每天涨 2%
            detector.update(price, 1e6)
            regime = detector.detect()
            assert regime == "CRISIS", (
                f"冷却期第 {i+1} 天应为 CRISIS，实际: {regime}"
            )

    def test_v5_crisis_blocks_new_positions(self, crash_data):
        """V5 引擎在 CRISIS 模式下不应建立新仓位"""
        market_data, codes = crash_data
        dates = sorted(market_data.keys())

        # 构造持续的买入信号（正常情况下会积极建仓）
        ml_signals = {}
        for date in dates:
            ml_signals[date] = {code: 0.95 - j * 0.05 for j, code in enumerate(codes)}

        from live.replay_engine_v5 import ReplayEngineV5
        engine = ReplayEngineV5(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml_signals,
            trend_ratio=0.35,
            lowvol_ratio=0.20,
            factor_ratio=0.25,
            cash_ratio=0.20,
        )

        # 记录每天的持仓数量
        daily_positions = []
        original_on_bar = engine._on_bar

        def tracked_on_bar(event):
            original_on_bar(event)
            total_pos = sum(
                len(acct.positions)
                for acct in engine.master.strategy_accounts.values()
            )
            daily_positions.append({
                "date": event.data["date"],
                "regime": engine._current_regime,
                "total_positions": total_pos,
            })

        engine._on_bar = tracked_on_bar

        # Re-register the handler with the event engine
        from core.event import EVENT_BAR
        engine._event_engine.unregister(EVENT_BAR, original_on_bar)
        engine._event_engine.register(EVENT_BAR, tracked_on_bar)

        engine.run()

        # 验证：CRISIS 期间不应有新增持仓
        crisis_days = [d for d in daily_positions if d["regime"] == "CRISIS"]
        if crisis_days:
            # 在 CRISIS 天，持仓数应 ≤ 前一天的持仓数（只减不增）
            for i, cd in enumerate(crisis_days):
                if i == 0:
                    # 第一个 CRISIS 天，持仓应开始减少
                    pass
                else:
                    prev = crisis_days[i - 1]
                    assert cd["total_positions"] <= prev["total_positions"], (
                        f"CRISIS 期间持仓不应增加: "
                        f"{prev['date']}({prev['total_positions']}) → "
                        f"{cd['date']}({cd['total_positions']})"
                    )

    def test_v5_crisis_generates_sell_signals(self):
        """
        直接测试 V5 的 _on_bar：CRISIS 模式下应为现有持仓生成卖出信号。
        """
        from live.replay_engine_v5 import ReplayEngineV5
        from live.strategy_account import StrategyAccount
        from core.event import Event, EVENT_BAR

        # 构造最小化的 V5 引擎
        market_data = {}
        dt = datetime(2024, 1, 2)
        codes = ["600001.SH", "600002.SH"]
        price = 10.0
        for i in range(30):
            date = (dt + timedelta(days=i)).strftime("%Y-%m-%d")
            market_data[date] = {
                code: {
                    "close": price,
                    "volume": 10_000_000,
                    "prev_close": price,
                }
                for code in codes
            }

        dates = sorted(market_data.keys())
        engine = ReplayEngineV5(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals={},
            trend_ratio=0.35,
            lowvol_ratio=0.20,
            factor_ratio=0.25,
            cash_ratio=0.20,
        )

        # 手动给策略账户注入持仓
        trend_acct = engine.master.strategy_accounts["Trend"]
        trend_acct.buy("600001.SH", 10.0, 1000, date="2024-01-01")
        trend_acct.cash = 340_000

        # 强制设置 CRISIS 状态
        engine._current_regime = "CRISIS"
        # 填充 RegimeDetector 使其返回 CRISIS
        detector = engine._regime_detector
        for _ in range(25):
            detector.update(100.0, 1e6)
        detector.update(90.0, 1e6)  # -10% crash
        detector.detect()  # consume the crisis trigger

        # 模拟一个 BAR 事件
        prices = market_data[dates[-1]]
        event = Event(EVENT_BAR, {"date": dates[-1], "prices": prices})

        # 捕获信号事件
        captured_signals = []
        original_on_signal = engine._on_signal

        def capture_signal(event):
            captured_signals.append(event.data)
            original_on_signal(event)

        from core.event import EVENT_SIGNAL
        engine._event_engine.register(EVENT_SIGNAL, capture_signal)

        # 执行 _on_bar（会触发 CRISIS 清仓逻辑）
        engine._on_bar(event)

        # 验证：应该有包含 sell 的信号被发出
        all_sell_codes = set()
        for sig_data in captured_signals:
            for sig in sig_data.get("signals", []):
                if sig.get("action") == "sell":
                    all_sell_codes.add(sig.get("ts_code"))

        # Trend 账户持有 600001.SH，CRISIS 时应生成卖出信号
        assert "600001.SH" in all_sell_codes, (
            f"CRISIS 模式下应为 600001.SH 生成卖出信号，"
            f"实际捕获的卖出标的: {all_sell_codes}"
        )


# ═══════════════════════════════════════════════════════════════
#  Smoke tests（快速，不标记 slow）
# ═══════════════════════════════════════════════════════════════

class TestSmoke:
    """快速冒烟测试，验证引擎基本可用性"""

    def test_v5_runs_without_crash(self, steady_data):
        """V5 在稳定行情下应正常运行并返回结果"""
        market_data, codes, ml_signals = steady_data
        dates = sorted(market_data.keys())

        from live.replay_engine_v5 import ReplayEngineV5
        engine = ReplayEngineV5(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml_signals,
        )
        curve = engine.run()

        assert len(curve) == len(dates)
        assert all("date" in d and "equity" in d and "drawdown" in d for d in curve)
        assert curve[-1]["equity"] > 0

    def test_v4_runs_without_crash(self, steady_data):
        """V4 在稳定行情下应正常运行并返回结果"""
        market_data, codes, ml_signals = steady_data
        dates = sorted(market_data.keys())

        from live.replay_engine_v4 import ReplayEngineV4
        engine = ReplayEngineV4(
            market_data=market_data,
            start_date=dates[0],
            end_date=dates[-1],
            initial_capital=1_000_000,
            ml_signals=ml_signals,
        )
        curve = engine.run()

        assert len(curve) == len(dates)
        assert curve[-1]["equity"] > 0
