from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SignalAction = Literal["BUY", "SELL", "HOLD"]


@dataclass(slots=True)
class Level:
    price: float
    volume: float


@dataclass(slots=True)
class QuoteSnapshot:
    symbol: str
    timestamp: str | None
    last_price: float
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    pre_close: float | None = None
    volume: float | None = None
    turnover: float | None = None
    bid: list[Level] = field(default_factory=list)
    ask: list[Level] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PositionSnapshot:
    symbol: str
    quantity: int
    available_quantity: int
    cost_basis: float | None = None
    last_price: float | None = None
    update_time: str | None = None


@dataclass(slots=True)
class SignalMetrics:
    last_price: float
    mid_price: float | None
    spread_bps: float | None
    imbalance: float | None
    momentum: float | None
    pnl_pct: float | None
    drawdown_pct: float | None


@dataclass(slots=True)
class SignalDecision:
    action: SignalAction
    score: float
    reason: str
    metrics: SignalMetrics
    suggested_shares: int = 0
