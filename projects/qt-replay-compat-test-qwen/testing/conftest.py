"""
conftest.py — 测试环境 fixtures
提供 vnpy mock（未安装时自动 patch）和公共 mock 数据生成工具。
"""
import sys
import queue
import types
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timedelta

import numpy as np
import pytest

# ── 确保项目根目录在 sys.path ───────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── vnpy mock ───────────────────────────────────────────────────
class _MockEvent:
    """Minimal vnpy Event replacement"""
    __slots__ = ("type_", "data")

    def __init__(self, type_: str = "", data=None):
        self.type_ = type_
        self.data = data


class _MockEventEngine:
    """Minimal vnpy EventEngine replacement (synchronous, no threads)"""

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._handlers: dict[str, list] = {}
        self._active = True

    def register(self, type_: str, handler):
        self._handlers.setdefault(type_, []).append(handler)

    def unregister(self, type_: str, handler):
        handlers = self._handlers.get(type_, [])
        if handler in handlers:
            handlers.remove(handler)

    def put(self, event: _MockEvent):
        self._queue.put(event)

    def _process(self, event: _MockEvent):
        for handler in self._handlers.get(event.type_, []):
            handler(event)

    def start(self):
        self._active = True

    def stop(self):
        self._active = False


def pytest_configure(config):
    """注册自定义 pytest marks"""
    config.addinivalue_line("markers", "slow: 标记为慢速测试，可通过 -m 'not slow' 跳过")


@pytest.fixture(autouse=True)
def _patch_vnpy(monkeypatch):
    """自动 patch vnpy 模块，使测试无需安装 vnpy"""
    vnpy_mod = types.ModuleType("vnpy")
    vnpy_event_mod = types.ModuleType("vnpy.event")
    vnpy_event_mod.Event = _MockEvent
    vnpy_event_mod.EventEngine = _MockEventEngine
    vnpy_mod.event = vnpy_event_mod

    monkeypatch.setitem(sys.modules, "vnpy", vnpy_mod)
    monkeypatch.setitem(sys.modules, "vnpy.event", vnpy_event_mod)


# ── Mock 数据生成工具 ───────────────────────────────────────────
def make_market_data(n_days=30, n_stocks=5, seed=42, start_price=10.0,
                     trend="crossover"):
    """
    构造 n_days 个交易日的 mock 行情数据。

    trend="crossover":
      前半段 MA20 < MA60（空头），后半段 MA20 > MA60（多头），
      产生清晰的 MA 交叉信号。
    trend="crash":
      正常行情后突然暴跌（触发 CRISIS）。
    trend="steady_up":
      稳定上涨（不触发 CRISIS）。
    """
    np.random.seed(seed)
    codes = [f"{600000 + i:06d}.SH" for i in range(n_stocks)]
    data = {}
    dt = datetime(2024, 1, 2)

    if trend == "crossover":
        # 前 15 天下跌（建立空头趋势），后 15 天上涨（多头反转）
        phases = (
            [("down", 15, -0.008, 0.012)],
            [("up", 15, 0.010, 0.008)],
        )
    elif trend == "crash":
        phases = (
            [("up", 20, 0.005, 0.008)],
            [("crash", 10, -0.045, 0.005)],
        )
    else:  # steady_up
        phases = (
            [("up", n_days, 0.005, 0.006)],
        )

    prices = {code: start_price + i * 2 for i, code in enumerate(codes)}
    day_idx = 0

    for phase_group in phases:
        for phase_name, phase_days, drift, vol in phase_group:
            for _ in range(phase_days):
                if day_idx >= n_days:
                    break
                date = (dt + timedelta(days=day_idx)).strftime("%Y-%m-%d")
                day = {}
                for code in codes:
                    prev = prices[code]
                    ret = drift + np.random.normal(0, vol)
                    close = round(max(prev * (1 + ret), 0.5), 2)
                    day[code] = {
                        "close": close,
                        "volume": int(np.random.uniform(5e6, 20e6)),
                        "prev_close": round(prev, 2),
                    }
                    prices[code] = close
                data[date] = day
                day_idx += 1

    return data, codes


def make_ml_signals(dates, codes, seed=42):
    """构造简单的 ML 因子信号（隔 5 天调仓，选 top 3）"""
    np.random.seed(seed)
    signals = {}
    for i, date in enumerate(dates):
        if i % 5 == 0:
            scores = {code: np.random.uniform(0, 1) for code in codes}
            signals[date] = scores
    return signals
