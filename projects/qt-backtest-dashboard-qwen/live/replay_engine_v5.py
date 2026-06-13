"""
ReplayEngineV5 — 事件驱动回测引擎

相比 V4 的变化:
- 内部走 EventEngine（core/event.py），为实盘异步行情推送做准备
- 策略通过 BaseStrategy / LegacyStrategyAdapter 接入，接口统一
- 对外保持向后兼容：run() 返回 equity_curve，与 V4 完全一致
- ExecutionEngine 升级为 v3（接入合约配置）

架构:
  DataFeed → EVENT_BAR → BarDispatcher
                              ↓
                    RegimeDetector → EVENT_REGIME
                              ↓
                    StrategyRunner（3策略）→ EVENT_SIGNAL
                              ↓
                    ExecutionEngine（3引擎）
                              ↓
                    PortfolioManager → equity_curve
"""
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.event import (
    Event, EventEngine,
    EVENT_BAR, EVENT_SIGNAL, EVENT_REGIME,
)
from core.strategy import LegacyStrategyAdapter
from live.execution_engine_v3 import ExecutionEngine
from live.strategy_account import StrategyAccount
from live.master_portfolio import MasterPortfolio
from live.regime_detector_v2 import RegimeDetectorV2
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.data_loader_fast import load_market_data_fast
from strategies.factor_strategy import FactorStrategy


class ReplayEngineV5:
    """
    事件驱动回测引擎（向后兼容 V4 接口）

    用法（与 V4 完全一致）:
        engine = ReplayEngineV5(market_data, start, end, ml_signals=ml_signals)
        curve = engine.run()
    """

    def __init__(
        self,
        market_data,
        start_date,
        end_date,
        initial_capital=1_000_000,
        ml_signals=None,
        trend_ratio=0.15,
        lowvol_ratio=0.15,
        factor_ratio=0.50,
        cash_ratio=0.20,
        factor_top_n=15,
        factor_rebalance_days=5,
    ):
        self.market_data = market_data
        self.start_date = start_date
        self.end_date = end_date
        self.ml_signals = ml_signals or {}
        self.initial_capital = initial_capital

        # ── 事件引擎（不启动 timer 线程，回测用同步模式）──
        self._event_engine = EventEngine()
        self._current_regime = "NEUTRAL"

        # ── 账户 & 组合 ──────────────────────────────────
        self.master = MasterPortfolio(initial_capital)

        trend_account  = StrategyAccount("Trend",  initial_capital * trend_ratio)
        lowvol_account = StrategyAccount("LowVol", initial_capital * lowvol_ratio)
        factor_account = StrategyAccount("Factor", initial_capital * factor_ratio)
        cash_account   = StrategyAccount("Cash",   initial_capital * cash_ratio)

        self.master.add_strategy("Trend",  trend_account)
        self.master.add_strategy("LowVol", lowvol_account)
        self.master.add_strategy("Factor", factor_account)
        self.master.add_strategy("Cash",   cash_account)

        # ── 执行引擎（v3，接入合约配置）─────────────────
        self._exec_engines = {
            "Trend":  ExecutionEngine(trend_account),
            "LowVol": ExecutionEngine(lowvol_account),
            "Factor": ExecutionEngine(factor_account),
        }

        # ── 策略（通过 LegacyStrategyAdapter 统一接口）──
        self._strategies = {
            "Trend":  LegacyStrategyAdapter("Trend",  TrendStrategyV2()),
            "LowVol": LegacyStrategyAdapter("LowVol", LowVolStrategy()),
            "Factor": LegacyStrategyAdapter("Factor", FactorStrategy(
                factor_scores=self.ml_signals,
                top_n=factor_top_n,
                rebalance_days=factor_rebalance_days,
            )),
        }

        # ── Regime 检测 ──────────────────────────────────
        self._regime_detector = RegimeDetectorV2()

        # ── 注册事件处理器 ────────────────────────────────
        self._event_engine.register(EVENT_BAR,    self._on_bar)
        self._event_engine.register(EVENT_REGIME, self._on_regime)
        self._event_engine.register(EVENT_SIGNAL, self._on_signal)

    # ── 公开接口（向后兼容 V4）───────────────────────────────
    def run(self) -> list[dict]:
        """
        运行回测，返回 equity_curve（与 V4 格式完全一致）
        [{"date": str, "equity": float, "drawdown": float}, ...]
        """
        dates = sorted(self.market_data.keys())
        warmup_dates = [d for d in dates if d < self.start_date]
        sim_dates    = [d for d in dates if self.start_date <= d <= self.end_date]
        total = len(sim_dates)

        # 预热期：更新策略内部状态，不产生信号
        for date in warmup_dates:
            prices = self.market_data[date]
            self._warmup_step(date, prices)

        # 初始化策略
        for strat in self._strategies.values():
            strat.initialize()

        # 模拟期：通过事件总线驱动
        for i, date in enumerate(sim_dates):
            prices = self.market_data[date]
            # 推送 BAR 事件，触发完整处理链
            self._event_engine.put(Event(EVENT_BAR, {"date": date, "prices": prices}))
            # 同步处理（回测模式：直接消费队列，不依赖后台线程）
            self._drain_events()

            if (i + 1) % 200 == 0:
                eq = self.master.total_equity
                dd = self.master.max_drawdown
                print(f"[V5] ({i+1}/{total}) equity={eq:,.0f} dd={dd:.2%}")

        return self.master.equity_curve

    # ── 事件处理器 ────────────────────────────────────────────
    def _on_bar(self, event: Event) -> None:
        date   = event.data["date"]
        prices = event.data["prices"]

        # 1. Regime 检测 → 推送 EVENT_REGIME
        regime = self._detect_regime(date, prices)
        if regime != self._current_regime:
            self._current_regime = regime
            self._event_engine.put(Event(EVENT_REGIME, {"regime": regime, "date": date}))
            self._drain_events()  # 确保 regime 先于 signal 处理

        # 2. 生成策略信号 → 推送 EVENT_SIGNAL
        for name, strat in self._strategies.items():
            strat.set_regime(regime)  # LowVol 需要 regime
            signals = strat.on_bars(date, prices)

            # Crisis 模式：强制清仓
            if regime == "CRISIS":
                account = self.master.strategy_accounts[name]
                signals = [{"action": "sell", "ts_code": c}
                           for c in list(account.positions.keys())]

            if signals:
                self._event_engine.put(Event(EVENT_SIGNAL, {
                    "strategy": name,
                    "signals":  signals,
                    "date":     date,
                    "prices":   prices,
                }))

        self._drain_events()

        # 3. Vol Target 缩放
        vol_leverage = self.master.get_vol_target_leverage()
        if vol_leverage < 1.0:
            for name, eng in self._exec_engines.items():
                for order in eng.pending_orders:
                    if order["action"] == "buy":
                        account = self.master.strategy_accounts[name]
                        order["target_cash"] = account.cash * vol_leverage

        # 4. 执行所有挂单
        for name, eng in self._exec_engines.items():
            eng.execute(prices, date=date)

        # 5. 估值
        for account in self.master.strategy_accounts.values():
            account.mark_to_market(prices)
        self.master.update_total_equity()

        # 6. 组合级回撤控制
        self.master.apply_drawdown_control(prices)

        # 7. 重新估值 & 记录
        for account in self.master.strategy_accounts.values():
            account.mark_to_market(prices)
        self.master.update_total_equity()
        self.master.record(date)

    def _on_regime(self, event: Event) -> None:
        """Regime 变更事件处理（当前仅记录，实盘可在此触发告警）"""
        regime = event.data["regime"]
        date   = event.data["date"]
        # 预留：实盘时可在此推送飞书通知
        # print(f"[V5] Regime changed → {regime} @ {date}")

    def _on_signal(self, event: Event) -> None:
        """信号事件：将信号挂入对应执行引擎的队列"""
        name    = event.data["strategy"]
        signals = event.data["signals"]
        eng     = self._exec_engines.get(name)
        if eng:
            eng.queue_orders(signals)

    # ── 内部工具 ──────────────────────────────────────────────
    def _drain_events(self) -> None:
        """
        同步消费事件队列（回测专用）
        实盘模式下 EventEngine 由后台线程消费，此方法不需要调用。
        """
        q = self._event_engine._queue
        while not q.empty():
            try:
                ev = q.get_nowait()
                self._event_engine._process(ev)
            except Exception:
                break

    def _warmup_step(self, date: str, prices: dict) -> None:
        """预热期：更新 Regime 检测器和策略内部状态"""
        closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
        if closes:
            self._regime_detector.update(np.mean(closes), 0)
        for strat in self._strategies.values():
            strat.warmup(date, prices)

    def _detect_regime(self, date: str, prices: dict) -> str:
        """Regime 检测（全市场均价代理）"""
        if prices:
            closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
            vols   = [d.get("volume", 0) for d in prices.values()]
            if closes:
                self._regime_detector.update(np.mean(closes), sum(vols))
                return self._regime_detector.detect()
        return "NEUTRAL"
