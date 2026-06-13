"""
信号生成器 v1
独立于回放引擎，每日收盘后运行一次，输出 JSON 格式交易信号。
用途：从回测系统走向交易系统的第一步。
"""

import json
import os
from datetime import datetime, timedelta

from live.data_loader import load_market_data
from live.trend_strategy_v2 import TrendStrategyV2
from live.lowvol_strategy_v2 import LowVolStrategy
from live.regime_detector_v2 import RegimeDetectorV2

SIGNAL_DIR = "logs/signals"
os.makedirs(SIGNAL_DIR, exist_ok=True)


def generate_signals(lookback_days=120):
    """
    基于最近 lookback_days 天的数据，生成明日交易信号。
    """
    today = datetime.now().date()
    start = (today - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    # 加载市场数据
    market_data = load_market_data(start, end)
    index_data = load_market_data(start, end, ts_code="000300.SH")

    if not market_data:
        print("❌ No market data available.")
        return None

    # 日期校验：最后一天数据是否为最近交易日（允许3天容差，覆盖周末和节假日）
    last_data_date = max(market_data.keys())
    days_gap = (today - datetime.strptime(last_data_date, "%Y-%m-%d").date()).days
    if days_gap > 3:
        print(f"⚠️ 数据可能过期：最后交易日 {last_data_date}，距今 {days_gap} 天")
        print("   请检查数据源是否正常更新。")
        return None

    # 初始化策略和检测器
    trend = TrendStrategyV2()
    lowvol = LowVolStrategy()
    regime_detector = RegimeDetectorV2()

    # 回放历史数据，让策略建立状态
    trend_signals = []
    lowvol_signals = []
    regime = "NEUTRAL"

    for date in sorted(market_data.keys()):
        prices = market_data[date]

        # 更新 regime
        if date in index_data and "000300.SH" in index_data[date]:
            idx = index_data[date]["000300.SH"]
            regime_detector.update(idx["close"], idx["volume"])
            regime = regime_detector.detect()

        # 生成信号（只保留最后一天的）
        trend_signals = trend.generate(date, prices)
        lowvol_signals = lowvol.generate(date, prices)

    # Crisis 状态下清空买入信号
    if regime == "CRISIS":
        trend_signals = [s for s in trend_signals if s["action"] == "sell"]
        lowvol_signals = [s for s in lowvol_signals if s["action"] == "sell"]

    # 构建输出
    output = {
        "generated_at": datetime.now().isoformat(),
        "signal_date": str(today),
        "regime": regime,
        "trend_signals": trend_signals,
        "lowvol_signals": lowvol_signals,
        "total_signals": len(trend_signals) + len(lowvol_signals),
    }

    # 保存
    filename = f"{today}.json"
    path = os.path.join(SIGNAL_DIR, filename)
    with open(path, "w") as f:
        json.dump(output, f, indent=4, default=str)

    print(f"✅ Signals generated: {path}")
    print(f"   Regime: {regime}")
    print(f"   Trend signals: {len(trend_signals)}")
    print(f"   LowVol signals: {len(lowvol_signals)}")

    return output


if __name__ == "__main__":
    generate_signals()
