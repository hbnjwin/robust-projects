from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .models import QuoteSnapshot


@dataclass(slots=True)
class PricePoint:
    price: float
    timestamp: float


@dataclass(slots=True)
class SymbolState:
    window_size: int
    points: deque[PricePoint] = field(init=False)
    intraday_high: float | None = None
    last_signal_ts: float = 0.0

    def __post_init__(self) -> None:
        self.points = deque(maxlen=self.window_size)

    def update(self, quote: QuoteSnapshot, epoch_seconds: float) -> None:
        self.points.append(PricePoint(price=quote.last_price, timestamp=epoch_seconds))
        if self.intraday_high is None or quote.last_price > self.intraday_high:
            self.intraday_high = quote.last_price

    def momentum(self) -> float | None:
        if len(self.points) < 2:
            return None
        first = self.points[0].price
        last = self.points[-1].price
        if first <= 0:
            return None
        return (last - first) / first

    def drawdown(self, last_price: float) -> float | None:
        if not self.intraday_high or self.intraday_high <= 0:
            return None
        return (last_price - self.intraday_high) / self.intraday_high
