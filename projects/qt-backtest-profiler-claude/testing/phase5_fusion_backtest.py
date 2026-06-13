"""
Phase 5: Factor + HIST 多 Alpha 融合回测
使用预计算的 HIST 信号矩阵（/vol1/mmap_cache/hist_bt/）
与 InlineFactorGenerator 融合，对比单独 Factor vs 融合效果

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/phase5_fusion_backtest.py
"""
import sys, os, json, time
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from live.replay_engine_v3 import ReplayEngineV3
from live.data_loader import load_market_data
from analytics.metrics_v2 import max_drawdown, annual_return, sharpe_ratio

# ── 配置 ──────────────────────────────────────────────────────
BACKTEST_START = "2024-07-01"
BACKTEST_END   = "2025-12-31"
INITIAL_CAP    = 1_000_000.0
MMAP_DIR       = "/vol1/mmap_cache/hist_bt"
OUT_PATH       = _ROOT / "data/backtest_compare/phase5_fusion.json"
os.makedirs(OUT_PATH.parent, exist_ok=True)

# ── 加载预计算 HIST 信号 ──────────────────────────────────────
print("加载预计算 HIST 信号矩阵 ...")
bt_dates     = np.load(f"{MMAP_DIR}/bt_dates.npy", allow_pickle=True)
hist_signals = np.load(f"{MMAP_DIR}/hist_signals.npy")  # [N_DATES, N_STOCKS]

# 构建 {date_str: {ts_code: score}} 字典
df_meta = pd.read_parquet(str(_ROOT / "data/factors_full.parquet"),
    filters=[("trade_date", ">=", date(2024, 3, 1)),
             ("trade_date", "<=", date(2025, 12, 31))],
    columns=["ts_code", "trade_date"])
df_meta["trade_date"] = pd.to_datetime(df_meta["trade_date"])
all_stocks = sorted(df_meta["ts_code"].unique())
stock2i = {s: i for i, s in enumerate(all_stocks)}

hist_signal_dict = {}
for di, d_str in enumerate(bt_dates):
    if d_str < BACKTEST_START or d_str > BACKTEST_END:
        continue
    row = hist_signals[di]
    valid = ~np.isnan(row)
    hist_signal_dict[d_str] = {
        all_stocks[si]: float(row[si])
        for si in np.where(valid)[0]
    }

print(f"HIST 信号: {len(hist_signal_dict)} 个交易日")


# ── 自定义 ReplayEngine：注入 HIST 信号 ──────────────────────
class ReplayEngineWithHIST(ReplayEngineV3):
    """
    继承 ReplayEngineV3，在 Factor Alpha 融合 HIST 信号
    """
    def __init__(self, hist_signals_dict, hist_weight, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hist_signals = hist_signals_dict
        self._hist_weight  = hist_weight
        self._factor_weight = 1.0 - hist_weight

    def _get_factor_scores(self, date, prices):
        """重写因子分数生成，融合 HIST"""
        from alpha.alpha_manager import AlphaManager
        from alpha.adapters.factor_alpha import FactorAlpha

        # InlineFactorGenerator 分数
        self.factor_gen.update(prices)
        factor_scores = self.factor_gen.compute_scores()

        # HIST 分数
        hist_scores = self._hist_signals.get(date, {})

        if not hist_scores:
            # 无 HIST 信号，退化为纯 Factor
            return factor_scores

        # AlphaManager 融合
        manager = AlphaManager(standardize="rank")
        manager.register(FactorAlpha({date: factor_scores}), weight=self._factor_weight)
        manager.register(FactorAlpha({date: hist_scores}),   weight=self._hist_weight)
        return manager.generate(date)


# ── 运行对比回测 ──────────────────────────────────────────────
def run_backtest(engine_cls, label, **engine_kwargs):
    print(f"\n{'='*50}")
    print(f"回测: {label}")
    market_data = load_market_data(BACKTEST_START, BACKTEST_END)
    engine = engine_cls(
        market_data=market_data,
        start_date=BACKTEST_START,
        end_date=BACKTEST_END,
        initial_capital=INITIAL_CAP,
        **engine_kwargs
    )

    # 如果是融合引擎，patch run() 里的因子分数生成
    if hasattr(engine, '_get_factor_scores'):
        _orig_run = engine.run

        def patched_run():
            from live.replay_engine_v3 import ReplayEngineV3
            # 直接调用父类 run，但在循环里替换因子分数
            for date_str, prices in engine.market_data.items():
                # 注入融合分数
                engine.factor_gen.update(prices)
                scores = engine._get_factor_scores(date_str, prices)
                engine.factor_strategy.factor_scores[date_str] = scores
            return _orig_run()

        # 不 patch，直接用 monkey-patch 方式替换 run 内部逻辑
        # 改为直接在 run() 里处理

    equity_curve = engine.run()
    equities = np.array([e["equity"] for e in equity_curve])

    ret   = round(equities[-1] / equities[0] - 1, 4)
    ann   = round(annual_return(equities), 4)
    sh    = round(sharpe_ratio(equities), 4)
    mdd   = round(max_drawdown(equities), 4)
    calmar = round(ann / mdd if mdd > 0 else 0, 3)

    print(f"  {label}: ret={ret*100:+.2f}% sharpe={sh:.3f} dd={mdd*100:.2f}%")
    return {"label": label, "total_return": ret, "annual_return": ann,
            "sharpe": sh, "max_drawdown": mdd, "calmar": calmar}


# ── 方案一：纯 Factor（基线）────────────────────────────────
print("\n方案一：纯 Factor（基线）")
market_data = load_market_data(BACKTEST_START, BACKTEST_END)
engine_factor = ReplayEngineV3(
    market_data=market_data,
    start_date=BACKTEST_START,
    end_date=BACKTEST_END,
    initial_capital=INITIAL_CAP,
)
eq_factor = engine_factor.run()
equities_f = np.array([e["equity"] for e in eq_factor])
r_factor = {
    "label": "Factor_only",
    "total_return": round(equities_f[-1] / equities_f[0] - 1, 4),
    "annual_return": round(annual_return(equities_f), 4),
    "sharpe": round(sharpe_ratio(equities_f), 4),
    "max_drawdown": round(max_drawdown(equities_f), 4),
}
r_factor["calmar"] = round(r_factor["annual_return"] / r_factor["max_drawdown"]
                           if r_factor["max_drawdown"] > 0 else 0, 3)
print(f"  Factor_only: ret={r_factor['total_return']*100:+.2f}% "
      f"sharpe={r_factor['sharpe']:.3f} dd={r_factor['max_drawdown']*100:.2f}%")


# ── 方案二：Factor(0.4) + HIST(0.6) 融合 ────────────────────
print("\n方案二：Factor(0.4) + HIST(0.6) 融合")

from alpha.alpha_manager import AlphaManager
from alpha.adapters.factor_alpha import FactorAlpha

market_data2 = load_market_data(BACKTEST_START, BACKTEST_END)
engine_fusion = ReplayEngineV3(
    market_data=market_data2,
    start_date=BACKTEST_START,
    end_date=BACKTEST_END,
    initial_capital=INITIAL_CAP,
)

# Monkey-patch：替换 run() 里的因子分数生成
_orig_run = engine_fusion.run.__func__

def fusion_run(self):
    from live.regime_detector_v2 import RegimeDetectorV2
    from live.adaptive_config import AdaptiveConfig
    from live.data_loader import load_market_data as _lmd

    index_data = self.index_data
    regime_detector = self.regime_detector

    for date_str, prices in self.market_data.items():
        # Regime 检测（复制原逻辑）
        if date_str in index_data and "000300.SH" in index_data[date_str]:
            index_close = index_data[date_str]["000300.SH"]["close"]
            index_vol   = index_data[date_str]["000300.SH"]["volume"]
            regime_detector.update(index_close, index_vol)
            regime = regime_detector.detect()
        else:
            regime = "NEUTRAL"

        adaptive_cfg = AdaptiveConfig.get_config(regime)
        self.factor_gen.factor_weights = adaptive_cfg["factor_weights"]
        self.trend.max_positions       = adaptive_cfg["trend_max_positions"]
        self.factor_strategy.top_n     = adaptive_cfg["factor_top_n"]
        self.lowvol.base_stop_loss     = adaptive_cfg["lowvol_base_stop_loss"]
        self.lowvol.base_cooldown      = adaptive_cfg["lowvol_base_cooldown"]
        self.lowvol.strategy_dd_limit  = adaptive_cfg.get("lowvol_strategy_dd_limit", 0.20)
        self.lowvol.set_regime(regime)
        self.factor_gen.set_regime(regime)

        trend_signals  = self.trend.generate(date_str, prices)
        lowvol_signals = self.lowvol.generate(date_str, prices)

        # ── 融合 Factor + HIST ──
        self.factor_gen.update(prices)
        factor_scores = self.factor_gen.compute_scores()
        hist_scores   = hist_signal_dict.get(date_str, {})

        if hist_scores:
            manager = AlphaManager(standardize="rank")
            manager.register(FactorAlpha({date_str: factor_scores}), weight=0.4)
            manager.register(FactorAlpha({date_str: hist_scores}),   weight=0.6)
            merged_scores = manager.generate(date_str)
        else:
            merged_scores = factor_scores

        self.factor_strategy.factor_scores[date_str] = merged_scores
        factor_signals = self.factor_strategy.generate(date_str, prices)

        # Crisis 处理
        if regime == "CRISIS":
            trend_signals = factor_signals = lowvol_signals = []
            for code in list(self.master.strategy_accounts["Trend"].positions.keys()):
                trend_signals.append({"action": "sell", "ts_code": code})
            for code in list(self.master.strategy_accounts["LowVol"].positions.keys()):
                lowvol_signals.append({"action": "sell", "ts_code": code})
            for code in list(self.master.strategy_accounts["Factor"].positions.keys()):
                factor_signals.append({"action": "sell", "ts_code": code})

        vol_leverage = self.master.get_vol_target_leverage()
        for sig in trend_signals + lowvol_signals + factor_signals:
            if sig["action"] == "buy" and vol_leverage < 1.0:
                acct_name = ("Trend" if sig in trend_signals else
                             "LowVol" if sig in lowvol_signals else "Factor")
                sig["target_cash"] = self.master.strategy_accounts[acct_name].cash * vol_leverage

        self.trend_engine.queue_orders(trend_signals)
        self.lowvol_engine.queue_orders(lowvol_signals)
        self.factor_engine.queue_orders(factor_signals)
        self.trend_engine.execute(prices, date=date_str)
        self.lowvol_engine.execute(prices, date=date_str)
        self.factor_engine.execute(prices, date=date_str)

        for account in self.master.strategy_accounts.values():
            account.mark_to_market(prices)
        self.master.update_total_equity()
        self.master.apply_drawdown_control(prices)
        for account in self.master.strategy_accounts.values():
            account.mark_to_market(prices)
        self.master.update_total_equity()
        self.master.record(date_str)

    return self.master.equity_curve

import types
engine_fusion.run = types.MethodType(fusion_run, engine_fusion)
eq_fusion = engine_fusion.run()
equities_fu = np.array([e["equity"] for e in eq_fusion])
r_fusion = {
    "label": "Factor0.4_HIST0.6_rank",
    "total_return": round(equities_fu[-1] / equities_fu[0] - 1, 4),
    "annual_return": round(annual_return(equities_fu), 4),
    "sharpe": round(sharpe_ratio(equities_fu), 4),
    "max_drawdown": round(max_drawdown(equities_fu), 4),
}
r_fusion["calmar"] = round(r_fusion["annual_return"] / r_fusion["max_drawdown"]
                           if r_fusion["max_drawdown"] > 0 else 0, 3)
print(f"  Factor0.4_HIST0.6: ret={r_fusion['total_return']*100:+.2f}% "
      f"sharpe={r_fusion['sharpe']:.3f} dd={r_fusion['max_drawdown']*100:.2f}%")


# ── 汇总输出 ─────────────────────────────────────────────────
print(f"\n{'='*65}")
print(f"{'模型':<30} {'总收益':>8} {'年化':>8} {'Sharpe':>8} {'最大回撤':>10} {'Calmar':>8}")
print(f"{'-'*65}")
for r in [r_factor, r_fusion]:
    print(f"{r['label']:<30} {r['total_return']*100:>7.2f}% "
          f"{r['annual_return']*100:>7.2f}% {r['sharpe']:>8.3f} "
          f"{r['max_drawdown']*100:>9.2f}% {r['calmar']:>8.3f}")

# 保存结果
result = {
    "generated_at": pd.Timestamp.now().isoformat(),
    "period": f"{BACKTEST_START} ~ {BACKTEST_END}",
    "factor_only": r_factor,
    "fusion_factor04_hist06": r_fusion,
}
with open(OUT_PATH, "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {OUT_PATH}")
