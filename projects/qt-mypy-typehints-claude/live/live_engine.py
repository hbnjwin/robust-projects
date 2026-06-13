"""
live/live_engine.py — 实盘主引擎

职责:
  - 每日定时拉取行情（腾讯接口）
  - 驱动三策略生成信号
  - 通过 Gateway 下单（Paper / QMT）
  - 收盘后触发撮合、估值、报告推送
  - 与 ReplayEngineV5 共用同一套策略/OMS/事件总线

切换实盘只需替换 gateway 参数:
  engine = LiveEngine(gateway=PaperGateway())   # 模拟盘
  engine = LiveEngine(gateway=QmtGateway())     # 招商 QMT（待接入）
"""
from __future__ import annotations

import sys
import numpy as np
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.event import EventEngine, Event, EVENT_BAR, EVENT_SIGNAL, EVENT_REGIME, EVENT_ORDER, EVENT_TRADE
from core.gateway import BaseGateway
from core.oms import OmsEngine, OrderSide
from core.portfolio_optimizer import PortfolioOptimizer, compute_cov_from_returns
from core.strategy import LegacyStrategyAdapter
from live.strategy_account import StrategyAccount
from live.master_portfolio import MasterPortfolio
from live.regime_detector_v2 import RegimeDetectorV2
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from strategies.factor_strategy import FactorStrategy


class LiveEngine:
    """
    实盘主引擎

    用法:
        from live.paper_gateway import PaperGateway
        gw = PaperGateway(initial_cash=1_000_000)
        engine = LiveEngine(gateway=gw, ml_signals=signals)
        engine.start()

        # 每日收盘后调用（可由调度器触发）:
        engine.on_market_close(date, prices)
    """

    def __init__(
        self,
        gateway: BaseGateway,
        initial_capital: float = 1_000_000,
        ml_signals: dict | None = None,
        trend_ratio:  float = 0.35,
        lowvol_ratio: float = 0.20,
        factor_ratio: float = 0.25,
        cash_ratio:   float = 0.20,
        factor_top_n: int = 15,
        factor_rebalance_days: int = 5,
        use_optimizer: bool = False,       # 是否启用组合优化器替换等权
        optimizer_method: str = "rp",      # inv/gmv/rp/mvo
    ):
        self.gateway = gateway
        self.initial_capital = initial_capital
        self.ml_signals = ml_signals or {}
        self.use_optimizer = use_optimizer
        self._optimizer = PortfolioOptimizer(method=optimizer_method) if use_optimizer else None
        self._price_history: dict[str, list[float]] = {}  # 用于协方差计算

        # ── 事件引擎 ──────────────────────────────────────────
        self._event_engine = EventEngine()
        self._current_regime = "NEUTRAL"

        # ── 账户 & 组合 ───────────────────────────────────────
        self.master = MasterPortfolio(initial_capital)

        trend_account  = StrategyAccount("Trend",  initial_capital * trend_ratio)
        lowvol_account = StrategyAccount("LowVol", initial_capital * lowvol_ratio)
        factor_account = StrategyAccount("Factor", initial_capital * factor_ratio)
        cash_account   = StrategyAccount("Cash",   initial_capital * cash_ratio)

        self.master.add_strategy("Trend",  trend_account)
        self.master.add_strategy("LowVol", lowvol_account)
        self.master.add_strategy("Factor", factor_account)
        self.master.add_strategy("Cash",   cash_account)

        # ── OMS ───────────────────────────────────────────────
        self._oms = OmsEngine(event_engine=self._event_engine)

        # ── 策略 ──────────────────────────────────────────────
        self._strategies = {
            "Trend":  LegacyStrategyAdapter("Trend",  TrendStrategyV2()),
            "LowVol": LegacyStrategyAdapter("LowVol", LowVolStrategy()),
            "Factor": LegacyStrategyAdapter("Factor", FactorStrategy(
                factor_scores=self.ml_signals,
                top_n=factor_top_n,
                rebalance_days=factor_rebalance_days,
            )),
        }   # ── Regime 检测 ───────────────────────────────────────
        self._regime_detector = RegimeDetectorV2()

        # ── 注册事件处理器 ─────────────────────────────────────
        self._event_engine.register(EVENT_BAR,    self._on_bar)
        self._event_engine.register(EVENT_SIGNAL, self._on_signal)
        self._event_engine.register(EVENT_REGIME, self._on_regime)
        self._event_engine.register(EVENT_ORDER,  self._on_order_event)
        self._event_engine.register(EVENT_TRADE,  self._on_trade_event)

        # ── Gateway 回调注入 ───────────────────────────────────
        self.gateway.on_order   = self._on_gateway_order
        self.gateway.on_trade   = self._on_gateway_trade
        self.gateway.on_account = self._on_gateway_account

        self._started = False
        self._warmup_done = False

    # ── 生命周期 ──────────────────────────────────────────────

    def start(self) -> None:
        """启动引擎，连接 Gateway"""
        if not self.gateway.connect():
            raise RuntimeError(f"Gateway 连接失败: {self.gateway.name}")
        self._started = True
        print(f"[LiveEngine] 启动成功，Gateway={self.gateway.name}")

    def stop(self) -> None:
        self.gateway.disconnect()
        self._started = False
        print("[LiveEngine] 已停止")

    def warmup(self, market_data: dict) -> None:
        """
        预热：用历史数据初始化策略内部状态（MA/动量等）
        market_data: {date: prices}，建议至少 60 个交易日
        """
        dates = sorted(market_data.keys())
        for date in dates:
            prices = market_data[date]
            closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
            if closes:
                self._regime_detector.update(np.mean(closes), 0)
            for strat in self._strategies.values():
                strat.warmup(date, prices)

        for strat in self._strategies.values():
            strat.initialize()

        self._warmup_done = True
        print(f"[LiveEngine] 预热完成，{len(dates)} 个交易日")

    # ── 每日主流程 ────────────────────────────────────────────

    def on_market_close(self, date: str, prices: dict) -> dict:
        """
        每日收盘后调用（由调度器触发）

        1. 推送 BAR 事件 → 策略生成信号 → OMS 下单
        2. Gateway 撮合（Paper: DailyMatcher；QMT: 真实成交回报）
        3. 估值 & 记录

        Returns: 当日摘要 dict
        """
        if not self._started:
            raise RuntimeError("请先调用 start()")

        # 推送 BAR 事件
        self._event_engine.put(Event(EVENT_BAR, {"date": date, "prices": prices}))
        self._drain_events()

        # Paper Gateway: 触发收盘撮合
        if hasattr(self.gateway, "on_daily_close"):
            self.gateway.on_daily_close(date, prices)

        # 同步 Gateway 持仓到 master（Paper 模式）
        self._sync_from_gateway(date, prices)

        # 估值 & 记录
        for account in self.master.strategy_accounts.values():
            account.mark_to_market(prices)
        self.master.update_total_equity()
        self.master.apply_drawdown_control(prices)
        for account in self.master.strategy_accounts.values():
            account.mark_to_market(prices)
        self.master.update_total_equity()
        self.master.record(date)

        eq = self.master.total_equity
        dd = self.master.max_drawdown
        print(f"[LiveEngine] [{date}] equity={eq:,.0f} dd={dd:.2%}")

        return {
            "date":         date,
            "total_equity": round(eq, 2),
            "max_drawdown": round(dd, 4),
            "positions":    sum(len(a.positions) for a in self.master.strategy_accounts.values()),
        }

    def get_signals_for_today(self, date: str, prices: dict) -> dict[str, list]:
        """
        生成今日信号（不下单，仅预览）
        返回 {strategy_name: [signal, ...]}
        """
        regime = self._detect_regime(date, prices)
        result = {}
        for name, strat in self._strategies.items():
            strat.set_regime(regime)
            signals = strat.on_bars(date, prices)
            if regime == "CRISIS":
                account = self.master.strategy_accounts[name]
                signals = [{"action": "sell", "ts_code": c}
                           for c in list(account.positions.keys())]
            result[name] = signals
        return result

    # ── 事件处理器 ────────────────────────────────────────────

    def _on_bar(self, event: Event) -> None:
        date   = event.data["date"]
        prices = event.data["prices"]

        regime = self._detect_regime(date, prices)
        if regime != self._current_regime:
            self._current_regime = regime
            self._event_engine.put(Event(EVENT_REGIME, {"regime": regime, "date": date}))
            self._drain_events()

        for name, strat in self._strategies.items():
            strat.set_regime(regime)
            signals = strat.on_bars(date, prices)

            if regime == "CRISIS":
                account = self.master.strategy_accounts[name]
                signals = [{"action": "sell", "ts_code": c}
                           for c in list(account.positions.keys())]

            for sig in signals:
                self._event_engine.put(Event(EVENT_SIGNAL, {
                    "strategy": name,
                    "signal":   sig,
                    "date":     date,
                    "prices":   prices,
                }))

        self._drain_events()

    def _on_signal(self, event: Event) -> None:
        """信号 → OMS 下单 → Gateway"""
        strategy = event.data["strategy"]
        sig      = event.data["signal"]
        date     = event.data["date"]
        prices   = event.data["prices"]

        ts_code = sig["ts_code"]
        if ts_code not in prices:
            return

        price  = prices[ts_code]["close"]
        action = sig["action"]

        account = self.master.strategy_accounts.get(strategy)
        if account is None:
            return

        if action == "buy":
            # 计算股数 — Regime 感知切换：BULL/NEUTRAL 用优化器，CRISIS 用等权
            regime_allows_opt = self._current_regime in ("BULL", "NEUTRAL")
            if self.use_optimizer and self._optimizer is not None and regime_allows_opt:
                opt_weight = self._get_optimizer_weight(strategy, ts_code, prices)
                target_cash = account.cash * opt_weight
            elif "weight" in sig:
                target_cash = account.cash * sig["weight"]
            elif "target_cash" in sig:
                target_cash = sig["target_cash"]
            else:
                target_cash = account.cash * 0.1  # 默认 10%

            shares = int(target_cash / (price * 1.001))
            shares = (shares // 100) * 100
            if shares <= 0:
                return

            order = self._oms.submit_order(
                strategy=strategy, ts_code=ts_code,
                side=OrderSide.BUY, price=price,
                volume=shares, date=date,
                raw_signal=sig,
            )
            self.gateway.send_order(order)

        elif action == "sell":
            if ts_code not in account.positions:
                return
            shares = account.positions[ts_code]["shares"]
            if shares <= 0:
                return

            order = self._oms.submit_order(
                strategy=strategy, ts_code=ts_code,
                side=OrderSide.SELL, price=price,
                volume=shares, date=date,
                raw_signal=sig,
            )
            self.gateway.send_order(order)

    def _get_optimizer_weight(self, strategy: str, ts_code: str, prices: dict) -> float:
        """用组合优化器计算单股权重，fallback 等权"""
        import pandas as pd

        account = self.master.strategy_accounts.get(strategy)
        if account is None:
            return 0.1

        # 更新价格历史
        for code, data in prices.items():
            if code not in self._price_history:
                self._price_history[code] = []
            self._price_history[code].append(data["close"])
            if len(self._price_history[code]) > 120:
                self._price_history[code] = self._price_history[code][-120:]

        # 当前持仓 + 本次买入候选
        held = list(account.positions.keys())
        candidates = list(set(held + [ts_code]))

        # 历史数据不足时 fallback 等权
        valid = [c for c in candidates if len(self._price_history.get(c, [])) >= 20]
        if len(valid) < 2:
            return 1.0 / max(len(candidates), 1)

        # 构建收益率 DataFrame
        min_len = min(len(self._price_history[c]) for c in valid)
        ret_data = {}
        for c in valid:
            prices_arr = self._price_history[c][-min_len:]
            rets = [prices_arr[i] / prices_arr[i-1] - 1 for i in range(1, len(prices_arr))]
            ret_data[c] = rets
        ret_df = pd.DataFrame(ret_data)

        # 计算协方差
        S = ret_df.cov()
        if S.isnull().any().any() or len(S) < 2:
            return 1.0 / len(valid)

        # 优化权重
        try:
            w = self._optimizer(S)
            weight = float(w.get(ts_code, 1.0 / len(valid)))
            # 单股上限 20%
            return min(weight, 0.20)
        except Exception:
            return 1.0 / len(valid)

    def _on_regime(self, event: Event) -> None:
        regime = event.data["regime"]
        date   = event.data["date"]
        print(f"[LiveEngine] Regime 切换 → {regime} @ {date}")

    def _on_order_event(self, event: Event) -> None:
        pass  # 预留：实盘可在此记录订单日志

    def _on_trade_event(self, event: Event) -> None:
        pass  # 预留：实盘可在此触发飞书通知

    # ── Gateway 回调 ──────────────────────────────────────────

    def _on_gateway_order(self, order_data: dict) -> None:
        """Gateway 订单回报（QMT 实盘用）"""
        pass

    def _on_gateway_trade(self, trade_data: dict) -> None:
        """Gateway 成交回报（QMT 实盘用）"""
        pass

    def _on_gateway_account(self, account_data: dict) -> None:
        """Gateway 账户更新"""
        pass

    # ── 内部工具 ──────────────────────────────────────────────

    def _drain_events(self) -> None:
        q = self._event_engine._queue
        while not q.empty():
            try:
                ev = q.get_nowait()
                self._event_engine._process(ev)
            except Exception:
                break

    def _detect_regime(self, date: str, prices: dict) -> str:
        if prices:
            closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
            vols   = [d.get("volume", 0) for d in prices.values()]
            if closes:
                self._regime_detector.update(np.mean(closes), sum(vols))
                return self._regime_detector.detect()
        return "NEUTRAL"

    def _sync_from_gateway(self, date: str, prices: dict) -> None:
        """
        Paper 模式：Gateway 内部账户已撮合，
        将结果同步回 master 各子账户（按策略分配）
        暂时跳过，Paper 模式下 master 账户独立运行
        """
        pass
