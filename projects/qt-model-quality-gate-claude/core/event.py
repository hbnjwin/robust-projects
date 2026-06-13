"""
core/event.py — 事件引擎封装
直接复用 vnpy EventEngine，扩展量化系统专用事件类型。

事件类型常量:
  EVENT_BAR      — 日线 Bar 推送（回测 & 实盘共用）
  EVENT_SIGNAL   — 策略信号
  EVENT_ORDER    — 订单状态变更
  EVENT_TRADE    — 成交回报
  EVENT_REGIME   — 市场状态切换
  EVENT_TIMER    — 定时器（继承自 vnpy）
"""
import sys
from pathlib import Path

# 复用 vnpy EventEngine
_VNPY_PATH = Path(__file__).resolve().parent.parent / "vnpy"
if str(_VNPY_PATH) not in sys.path:
    sys.path.insert(0, str(_VNPY_PATH))

from vnpy.event import Event, EventEngine  # noqa: F401  re-export

# ── 量化系统专用事件类型 ──────────────────────────────────────
EVENT_BAR    = "eBar"       # data: {"date": str, "prices": dict}
EVENT_SIGNAL = "eSignal"    # data: {"strategy": str, "signals": list}
EVENT_ORDER  = "eOrder"     # data: order dict
EVENT_TRADE  = "eTrade"     # data: trade dict
EVENT_REGIME = "eRegime"    # data: {"regime": str, "date": str}
EVENT_TIMER  = "eTimer"     # 继承自 vnpy（1s 定时器）

__all__ = [
    "Event",
    "EventEngine",
    "EVENT_BAR",
    "EVENT_SIGNAL",
    "EVENT_ORDER",
    "EVENT_TRADE",
    "EVENT_REGIME",
    "EVENT_TIMER",
]
