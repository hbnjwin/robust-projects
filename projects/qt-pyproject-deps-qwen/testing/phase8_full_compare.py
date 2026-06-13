"""
Phase 8: 全组合对比回测
测试 Vol Scaling / Regime 动态权重 / HIST 融合 的各种组合

用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/phase8_full_compare.py
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from live.data_loader import load_market_data
from live.replay_engine_v3 import ReplayEngineV3
from analytics.metrics_v2 import max_drawdown, annual_return, sharpe_ratio

START = "2024-07-01"
END   = "2025-12-31"
CAP   = 1_000_000

print(f"加载市场数据 {START} ~ {END} ...")
market_data = load_market_data(START, END)
print(f"  交易日: {len(market_data)}")


def run(label, use_fusion, vol_scaling, use_regime_weights):
    print(f"\n{'='*50}")
    print(f"回测: {label}")

    engine = ReplayEngineV3(
        market_data=market_data,
        start_date=START,
        end_date=END,
        initial_capital=CAP,
    )

    engine._use_fusion              = use_fusion
    engine.factor_strategy.vol_scaling = vol_scaling
    engine.use_regime_weights       = use_regime_weights

    eq_curve = engine.run()
    equities = np.array([e["equity"] for e in eq_curve])

    r = {
        "label":          label,
        "total_return":   round(equities[-1] / equities[0] - 1, 4),
        "annual_return":  round(annual_return(equities), 4),
        "sharpe":         round(sharpe_ratio(equities), 4),
        "max_drawdown":   round(max_drawdown(equities), 4),
        "vol_scaling":    vol_scaling,
        "use_fusion":     use_fusion,
        "use_regime":     use_regime_weights,
    }
    r["calmar"] = round(r["annual_return"] / r["max_drawdown"], 3) if r["max_drawdown"] > 0 else 0

    print(f"  {label}: ret={r['total_return']*100:+.2f}% sharpe={r['sharpe']:.3f} dd={r['max_drawdown']*100:.2f}%")
    return r


results = [
    run("A: 等权+无融合",            use_fusion=False, vol_scaling=False, use_regime_weights=False),
    run("B: VolScale+无融合",         use_fusion=False, vol_scaling=True,  use_regime_weights=False),
    run("C: VolScale+固定融合",       use_fusion=True,  vol_scaling=True,  use_regime_weights=False),
    run("D: VolScale+Regime+HIST",    use_fusion=True,  vol_scaling=True,  use_regime_weights=True),
]

print(f"\n{'='*70}")
print(f"{'组合':<28} {'总收益':>8} {'Sharpe':>8} {'MDD':>8} {'Calmar':>8}")
print(f"{'-'*70}")
for r in results:
    print(f"{r['label']:<28} {r['total_return']*100:>7.2f}% "
          f"{r['sharpe']:>8.3f} {r['max_drawdown']*100:>7.2f}% {r['calmar']:>8.3f}")

out = _ROOT / "data/backtest_compare/phase8_full_compare.json"
out.parent.mkdir(exist_ok=True)
with open(out, "w") as f:
    json.dump({
        "generated_at": pd.Timestamp.now().isoformat(),
        "period": f"{START} ~ {END}",
        "results": results,
    }, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {out}")
