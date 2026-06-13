"""
ReplayEngineV4 - ML信号驱动回测引擎

相比 V3 的变化:
- FactorStrategy 的信号源: InlineFactorGenerator → MLSignalGenerator (预计算信号)
- 不再需要 AdaptiveConfig 的手工因子权重
- 保留: RegimeDetectorV2, ExecutionEngine, MasterPortfolio, LowVolStrategy, TrendStrategy
"""
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.strategy_account import StrategyAccount
from live.master_portfolio import MasterPortfolio
from live.execution_engine_v2 import ExecutionEngine
from live.regime_detector_v2 import RegimeDetectorV2
from live.data_loader_fast import load_market_data_fast
from strategies.factor_strategy import FactorStrategy


class ReplayEngineV4:
    """
    ML 信号驱动回测引擎

    用法:
        from signals.signal_generator import MLSignalGenerator
        gen = MLSignalGenerator(...)
        ml_signals = gen.get_all_signals()

        engine = ReplayEngineV4(market_data, start, end, ml_signals=ml_signals)
        curve = engine.run()
    """

    def __init__(
        self,
        market_data,
        start_date,
        end_date,
        initial_capital=1_000_000,
        ml_signals=None,
        # 资金分配比例
        trend_ratio=0.35,
        lowvol_ratio=0.20,
        factor_ratio=0.25,
        cash_ratio=0.20,
        # ML-Factor 策略参数
        factor_top_n=15,
        factor_rebalance_days=5,
    ):
        self.market_data = market_data
        self.start_date = start_date
        self.end_date = end_date
        self.ml_signals = ml_signals or {}

        self.master = MasterPortfolio(initial_capital)

        # 资金分配
        trend_account = StrategyAccount("Trend", initial_capital * trend_ratio)
        lowvol_account = StrategyAccount("LowVol", initial_capital * lowvol_ratio)
        factor_account = StrategyAccount("Factor", initial_capital * factor_ratio)
        cash_account = StrategyAccount("Cash", initial_capital * cash_ratio)

        self.master.add_strategy("Trend", trend_account)
        self.master.add_strategy("LowVol", lowvol_account)
        self.master.add_strategy("Factor", factor_account)
        self.master.add_strategy("Cash", cash_account)

        # 策略实例
        self.trend = TrendStrategyV2()
        self.lowvol = LowVolStrategy()

        # ML-Factor 策略：用预计算的 ML 信号
        self.factor_strategy = FactorStrategy(
            factor_scores=self.ml_signals,
            top_n=factor_top_n,
            rebalance_days=factor_rebalance_days,
        )

        # 执行引擎
        self.trend_engine = ExecutionEngine(trend_account)
        self.lowvol_engine = ExecutionEngine(lowvol_account)
        self.factor_engine = ExecutionEngine(factor_account)

        # Regime 检测（用全市场均价代理，无独立指数数据）
        self.index_data = {}
        self.regime_detector = RegimeDetectorV2()
        self._use_market_proxy = True

    def run(self):
        dates = sorted(self.market_data.keys())
        total = len(dates)

        for i, date in enumerate(dates):
            prices = self.market_data[date]

            # 1. Regime 检测
            regime = self._detect_regime(date, prices)

            # 2. Regime 感知参数调整（简化版，只调 Trend/LowVol）
            self._apply_regime_config(regime)

            # 3. 生成策略信号
            trend_signals = self.trend.generate(date, prices)
            lowvol_signals = self.lowvol.generate(date, prices)
            factor_signals = self.factor_strategy.generate(date, prices)

            # 4. Crisis 行为：阻止新信号 + 主动清仓
            if regime == "CRISIS":
                trend_signals = self._crisis_liquidate("Trend")
                lowvol_signals = self._crisis_liquidate("LowVol")
                factor_signals = self._crisis_liquidate("Factor")

            # 5. Vol Target
            vol_leverage = self.master.get_vol_target_leverage()
            if vol_leverage < 1.0:
                self._apply_vol_target(trend_signals, "Trend", vol_leverage)
                self._apply_vol_target(lowvol_signals, "LowVol", vol_leverage)
                self._apply_vol_target(factor_signals, "Factor", vol_leverage)

            # 6. 执行
            self.trend_engine.queue_orders(trend_signals)
            self.lowvol_engine.queue_orders(lowvol_signals)
            self.factor_engine.queue_orders(factor_signals)

            self.trend_engine.execute(prices, date=date)
            self.lowvol_engine.execute(prices, date=date)
            self.factor_engine.execute(prices, date=date)

            # 7. 估值
            for account in self.master.strategy_accounts.values():
                account.mark_to_market(prices)
            self.master.update_total_equity()

            # 8. 组合级回撤控制
            self.master.apply_drawdown_control(prices)

            # 9. 重新估值
            for account in self.master.strategy_accounts.values():
                account.mark_to_market(prices)
            self.master.update_total_equity()
            self.master.record(date)

            if (i + 1) % 200 == 0:
                eq = self.master.total_equity
                dd = self.master.max_drawdown
                print(f"[V4] ({i+1}/{total}) equity={eq:,.0f} dd={dd:.2%}")

        return self.master.equity_curve

    def _detect_regime(self, date, prices):
        """Regime 检测：优先用指数数据，否则用全市场均价"""
        if not self._use_market_proxy:
            if date in self.index_data and "000300.SH" in self.index_data[date]:
                idx = self.index_data[date]["000300.SH"]
                self.regime_detector.update(idx["close"], idx.get("volume", 0))
                return self.regime_detector.detect()

        # 全市场均价代理
        if prices:
            closes = [d["close"] for d in prices.values() if d.get("close", 0) > 0]
            vols = [d.get("volume", 0) for d in prices.values()]
            if closes:
                import numpy as np
                self.regime_detector.update(np.mean(closes), sum(vols))
                return self.regime_detector.detect()

        return "NEUTRAL"

    def _apply_regime_config(self, regime):
        """简化版 Regime 参数调整（只调 Trend/LowVol，Factor 由 ML 模型内部处理）"""
        if regime == "BULL":
            self.trend.max_positions = 15
            self.lowvol.base_stop_loss = 0.08
        elif regime == "CRISIS":
            self.trend.max_positions = 5
            self.lowvol.base_stop_loss = 0.08
        else:
            self.trend.max_positions = 10
            self.lowvol.base_stop_loss = 0.12

        self.lowvol.set_regime(regime)

    def _crisis_liquidate(self, strategy_name):
        """Crisis 模式：生成清仓信号"""
        account = self.master.strategy_accounts[strategy_name]
        signals = []
        for code in list(account.positions.keys()):
            signals.append({"action": "sell", "ts_code": code})
        return signals

    def _apply_vol_target(self, signals, strategy_name, vol_leverage):
        """Vol Target：缩减买入仓位"""
        account = self.master.strategy_accounts[strategy_name]
        for signal in signals:
            if signal["action"] == "buy":
                signal["target_cash"] = account.cash * vol_leverage
