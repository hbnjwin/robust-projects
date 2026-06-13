"""
Phase 5: ReplayEngineV3 融合 vs 纯 Factor 对比回测
用法:
    cd /home/tulin/quant
    source .venv/bin/activate
    python testing/phase5_replay_compare.py
"""
import sys, json
from pathlib import Path
import numpy as np

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


def run(label, use_fusion):
    print(f"\n{'='*50}")
    print(f"回测: {label}")

    # 控制是否使用融合信号
    engine = ReplayEngineV3(
        market_data=market_data,
        start_date=START,
        end_date=END,
        initial_capital=CAP,
    )

    if not use_fusion:
        # 强制关闭融合，退化为纯 InlineFactorGenerator
        engine._use_fusion = False

    eq_curve = engine.run()
    equities = np.array([e["equity"] for e in eq_curve])

    r = {
        "label": label,
        "total_return": round(equities[-1] / equities[0] - 1, 4),
        "annual_return": round(annual_return(equities), 4),
        "sharpe":        round(sharpe_ratio(equities), 4),
        "max_drawdown":  round(max_drawdown(equities), 4),
    }
    r["calmar"] = round(r["annual_return"] / r["max_drawdown"], 3) if r["max_drawdown"] > 0 else 0

    # 各策略账户
    for name, acct in engine.master.strategy_accounts.items():
        r[f"{name}_equity"] = round(acct.total_equity, 2)

    print(f"  {label}: ret={r['total_return']*100:+.2f}% sharpe={r['sharpe']:.3f} dd={r['max_drawdown']*100:.2f}%")
    return r


r_factor = run("Factor_only",        use_fusion=False)
r_fusion = run("Factor0.4_HIST0.6",  use_fusion=True)

print(f"\n{'='*65}")
print(f"{'模型':<28} {'总收益':>8} {'年化':>8} {'Sharpe':>8} {'最大回撤':>10} {'Calmar':>8}")
print(f"{'-'*65}")
for r in [r_factor, r_fusion]:
    print(f"{r['label']:<28} {r['total_return']*100:>7.2f}% "
          f"{r['annual_return']*100:>7.2f}% {r['sharpe']:>8.3f} "
          f"{r['max_drawdown']*100:>9.2f}% {r['calmar']:>8.3f}")

out = _ROOT / "data/backtest_compare/phase5_replay_compare.json"
out.parent.mkdir(exist_ok=True)
import pandas as pd
with open(out, "w") as f:
    json.dump({
        "generated_at": pd.Timestamp.now().isoformat(),
        "period": f"{START} ~ {END}",
        "factor_only": r_factor,
        "fusion": r_fusion,
    }, f, indent=2, ensure_ascii=False)
print(f"\n✅ 结果已保存: {out}")
