"""
run_14day_stability.py — 14天稳定性回测
使用 ReplayEngineV5 + 真实策略（TrendV2 / LowVol / Factor）
"""
import sys
import json
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from live.data_loader import load_market_data
from live.replay_engine_v5 import ReplayEngineV5

def load_latest_ml_signals() -> dict:
    """加载最近一个交易日的 ML 信号"""
    signals_dir = Path("/home/tulin/quant/data/signals")
    if not signals_dir.exists():
        return {}
    files = sorted(signals_dir.glob("*.json"), reverse=True)
    for f in files[:5]:
        try:
            d = json.loads(f.read_text())
            sigs = d.get("all_signals", {})
            if sigs:
                print(f"  ML signals loaded: {f.name} ({len(sigs)} stocks)")
                return sigs
        except Exception:
            continue
    return {}


def run():
    today = datetime.date.today()
    # 取最近 30 个自然日（覆盖约 20 个交易日）
    start = (today - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    # 回测窗口：最近 14 个交易日
    eval_start = (today - datetime.timedelta(days=20)).strftime("%Y-%m-%d")

    print(f"=== 14 Day Stability Simulation ===")
    print(f"  数据范围: {start} ~ {end}")
    print(f"  评估窗口: {eval_start} ~ {end}")

    # 加载行情
    market_data = load_market_data(start, end)
    if not market_data:
        print("❌ 行情数据为空，退出")
        return

    trading_days = sorted(market_data.keys())
    print(f"  交易日数: {len(trading_days)}")

    # 加载 ML 信号
    ml_signals = load_latest_ml_signals()

    # 运行 ReplayEngineV5
    engine = ReplayEngineV5(
        market_data=market_data,
        start_date=eval_start,
        end_date=end,
        ml_signals=ml_signals,
    )
    curve = engine.run()

    if not curve:
        print("❌ 回测结果为空")
        return

    import pandas as pd
    df = pd.DataFrame(curve)

    final_equity  = df.iloc[-1]["equity"]
    max_drawdown  = df["drawdown"].max() if "drawdown" in df.columns else 0.0
    min_equity    = df["equity"].min()
    trade_days    = len(df)
    total_return  = (final_equity - 1_000_000) / 1_000_000 * 100

    print(f"\n=== 回测结果 ===")
    print(f"  交易日数:   {trade_days}")
    print(f"  期末净值:   {final_equity:,.2f}")
    print(f"  总收益率:   {total_return:+.2f}%")
    print(f"  最大回撤:   {max_drawdown:.2%}")
    print(f"  最低净值:   {min_equity:,.2f}")

    # 写入 task_state
    tz = datetime.timezone(datetime.timedelta(hours=8))
    status = "success" if trade_days > 0 else "warning"
    state = {
        "last_run":     datetime.datetime.now(tz).isoformat(),
        "status":       status,
        "error":        "",
        "trade_days":   trade_days,
        "final_equity": round(final_equity, 2),
        "total_return": round(total_return, 4),
        "max_drawdown": round(float(max_drawdown), 4),
        "eval_start":   eval_start,
        "eval_end":     end,
    }
    Path("/home/tulin/quant/control/task_state/daily_stability.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2)
    )
    print("  task_state written ✅")
    return state


if __name__ == "__main__":
    run()
