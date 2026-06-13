from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.strategy_account import StrategyAccount
from live.master_portfolio import MasterPortfolio
from live.execution_engine_v2 import ExecutionEngine
from live.regime_detector_v2 import RegimeDetectorV2
from live.data_loader import load_market_data
from live.inline_factor_generator import InlineFactorGenerator
from live.adaptive_config import AdaptiveConfig
from strategies.factor_strategy import FactorStrategy

import os
import numpy as np

_MMAP_DIR = "/vol1/mmap_cache/hist_bt"


def _load_precomputed_signals():
    """
    加载预计算的 HIST + Factor 信号矩阵
    返回 (hist_dict, factor_dict) 各为 {date_str: {ts_code: score}}
    如果缓存不存在则返回 (None, None)
    """
    dates_path  = os.path.join(_MMAP_DIR, "bt_dates.npy")
    hist_path   = os.path.join(_MMAP_DIR, "hist_signals.npy")
    factor_path = os.path.join(_MMAP_DIR, "factor_signals.npy")

    if not all(os.path.exists(p) for p in [dates_path, hist_path, factor_path]):
        return None, None

    try:
        import pandas as pd
        from pathlib import Path

        bt_dates     = np.load(dates_path, allow_pickle=True)
        hist_mat     = np.load(hist_path)
        factor_mat   = np.load(factor_path)

        # 加载股票列表（与预计算时一致）
        factors_full = Path("/home/tulin/quant/data/factors_full.parquet")
        if not factors_full.exists():
            return None, None

        from datetime import date as _date
        df_meta = pd.read_parquet(str(factors_full),
            filters=[("trade_date", ">=", _date(2024, 3, 1))],
            columns=["ts_code"])
        all_stocks = sorted(df_meta["ts_code"].unique())

        hist_dict   = {}
        factor_dict = {}

        for di, d_str in enumerate(bt_dates):
            d_str = str(d_str)
            h_row = hist_mat[di]
            f_row = factor_mat[di]

            h_valid = ~np.isnan(h_row)
            f_valid = ~np.isnan(f_row)

            if h_valid.any():
                hist_dict[d_str] = {
                    all_stocks[si]: float(h_row[si])
                    for si in np.where(h_valid)[0]
                    if si < len(all_stocks)
                }
            if f_valid.any():
                factor_dict[d_str] = {
                    all_stocks[si]: float(f_row[si])
                    for si in np.where(f_valid)[0]
                    if si < len(all_stocks)
                }

        print(f"[ReplayV3] 预计算信号加载完成: HIST {len(hist_dict)}天, Factor {len(factor_dict)}天")
        return hist_dict, factor_dict

    except Exception as e:
        print(f"[ReplayV3] 预计算信号加载失败: {e}，使用 InlineFactorGenerator")
        e, None


class ReplayEngineV3:

    def __init__(self, market_data, start_date, end_date, initial_capital=1_000_000):
        self.market_data = market_data
        self.start_date = start_date
        self.end_date = end_date

        self.master = MasterPortfolio(initial_capital)

        # 优化4：资金分配 Trend 40% / LowVol 25% / Factor 15% / Cash 20%
        trend_account = StrategyAccount("Trend", initial_capital * 0.40)
        lowvol_account = StrategyAccount("LowVol", initial_capital * 0.25)
        factor_account = StrategyAccount("Factor", initial_capital * 0.15)
        cash_account = StrategyAccount("Cash", initial_capital * 0.20)

        self.master.add_strategy("Trend", trend_account)
        self.master.add_strategy("LowVol", lowvol_account)
        self.master.add_strategy("Factor", factor_account)
        self.master.add_strategy("Cash", cash_account)

        self.trend = TrendStrategyV2()
        self.lowvol = LowVolStrategy()

        # 优化4：因子策略（使用内联因子生成器作为 fallback）
        self.factor_gen = InlineFactorGenerator()
        # Phase 5 参数优化：top_n=20, rebalance_days=30（Monte Carlo 扫描最优，Sharpe 1.366）
        self.factor_strategy = FactorStrategy(factor_scores={}, top_n=20, rebalance_days=30)

        # Phase 5: 加载预计算 HIST + Factor 信号（用于融合回测）
        self._hist_cache, self._factor_cache = _load_precomputed_signals()
        self._use_fusion = (self._hist_cache is not None and self._factor_cache is not None)
        # Phase 8: Regime 动态权重开关（默认开启）
        self.use_regime_weights = True

        self.trend_engine = ExecutionEngine(trend_account)
        self.lowvol_engine = ExecutionEngine(lowvol_account)
        self.factor_engine = ExecutionEngine(factor_account)

        self.index_data = load_market_data(start_date, end_date, ts_code="000300.SH")
        self.regime_detector = RegimeDetectorV2()

    def run(self):
        for date, prices in self.market_data.items():

            # 1. 更新指数数据 & 检测 regime
            if date in self.index_data and "000300.SH" in self.index_data[date]:
                index_close = self.index_data[date]["000300.SH"]["close"]
                index_vol = self.index_data[date]["000300.SH"]["volume"]
                self.regime_detector.update(index_close, index_vol)
                regime = self.regime_detector.detect()
            else:
                regime = "NEUTRAL"

            # 2. 自适应配置：根据 Regime 动态调整各策略参数
            adaptive_cfg = AdaptiveConfig.get_config(regime)
            self.factor_gen.factor_weights = adaptive_cfg["factor_weights"]
            self.trend.max_positions = adaptive_cfg["trend_max_positions"]
            self.factor_strategy.top_n = adaptive_cfg["factor_top_n"]
            self.lowvol.base_stop_loss = adaptive_cfg["lowvol_base_stop_loss"]
            self.lowvol.base_cooldown = adaptive_cfg["lowvol_base_cooldown"]
            self.lowvol.strategy_dd_limit = adaptive_cfg.get("lowvol_strategy_dd_limit", 0.20)

            # 注入 Regime 到自适应止损策略和因子生成器
            self.lowvol.set_regime(regime)
            self.factor_gen.set_regime(regime)

            # 3. 生成策略信号
            trend_signals = self.trend.generate(date, prices)
            lowvol_signals = self.lowvol.generate(date, prices)

            # ===== Phase 5: Factor + HIST 融合 Alpha =====
            self.factor_gen.update(prices)

            if self._use_fusion:
                # Phase 6/8: 融合权重（Regime 动态 or 固定）
                if self.use_regime_weights:
                    _regime_weights = {
                        "BULL":    (0.1, 0.9),
                        "NEUTRAL": (0.6, 0.4),
                        "CRISIS":  (0.5, 0.5),
                    }
                    fw, hw = _regime_weights.get(regime, (0.4, 0.6))
                else:
                    fw, hw = 0.4, 0.6  # 固定权重

                factor_scores = self._factor_cache.get(date, {})
                hist_scores   = self._hist_cache.get(date, {})

                if factor_scores and hist_scores:
                    from alpha.alpha_manager import AlphaManager
                    from alpha.adapters.factor_alpha import FactorAlpha
                    manager = AlphaManager(standardize="rank")
                    manager.register(FactorAlpha({date: factor_scores}), weight=fw)
                    manager.register(FactorAlpha({date: hist_scores}),   weight=hw)
                    wrapped_scores = manager.generate(date)
                elif factor_scores:
                    wrapped_scores = factor_scores
                else:
                    wrapped_scores = self.factor_gen.compute_scores()
            else:
                # 无预计算缓存：使用 InlineFactorGenerator
                wrapped_scores = self.factor_gen.compute_scores()

            self.factor_strategy.factor_scores[date] = wrapped_scores
            # ================================================

            factor_signals = self.factor_strategy.generate(date, prices)

            # 3. Crisis 行为：阻止新信号 + 主动减仓已有持仓
            if regime == "CRISIS":
                trend_signals = []
                lowvol_signals = []
                factor_signals = []
                # 主动卖出所有持仓
                for code in list(self.master.strategy_accounts["Trend"].positions.keys()):
                    trend_signals.append({"action": "sell", "ts_code": code})
                for code in list(self.master.strategy_accounts["LowVol"].positions.keys()):
                    lowvol_signals.append({"action": "sell", "ts_code": code})
                for code in list(self.master.strategy_accounts["Factor"].positions.keys()):
                    factor_signals.append({"action": "sell", "ts_code": code})

            # 4. Vol Target：根据当前波动率调整新买入订单的仓位
            vol_leverage = self.master.get_vol_target_leverage()
            for signal in trend_signals:
                if signal["action"] == "buy" and vol_leverage < 1.0:
                    signal["target_cash"] = self.master.strategy_accounts["Trend"].cash * vol_leverage
            for signal in lowvol_signals:
                if signal["action"] == "buy" and vol_leverage < 1.0:
                    signal["target_cash"] = self.master.strategy_accounts["LowVol"].cash * vol_leverage
            for signal in factor_signals:
                if signal["action"] == "buy" and vol_leverage < 1.0:
                    signal["target_cash"] = self.master.strategy_accounts["Factor"].cash * vol_leverage

            # 5. 执行
            self.trend_engine.queue_orders(trend_signals)
            self.lowvol_engine.queue_orders(lowvol_signals)
            self.factor_engine.queue_orders(factor_signals)

            self.trend_engine.execute(prices, date=date)
            self.lowvol_engine.execute(prices, date=date)
            self.factor_engine.execute(prices, date=date)

            # 6. 估值
            for account in self.master.strategy_accounts.values():
                account.mark_to_market(prices)

            self.master.update_total_equity()

            # 7. 组合级回撤控制（通过真实卖出）
            self.master.apply_drawdown_control(prices)

            # 8. 重新估值
            for account in self.master.strategy_accounts.values():
                account.mark_to_market(prices)

            self.master.update_total_equity()
            self.master.record(date)

        return self.master.equity_curve
