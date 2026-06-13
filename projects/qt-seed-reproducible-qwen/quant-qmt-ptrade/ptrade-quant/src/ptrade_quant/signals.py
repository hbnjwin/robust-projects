from __future__ import annotations

import math
import time

from .config import SignalConfig
from .models import PositionSnapshot, QuoteSnapshot, SignalDecision, SignalMetrics
from .state import SymbolState


def _sum_volume(levels: list) -> float:
    return sum(max(level.volume, 0.0) for level in levels)


def _mid_price(quote: QuoteSnapshot) -> float | None:
    if quote.bid and quote.ask:
        return (quote.bid[0].price + quote.ask[0].price) / 2.0
    return quote.last_price if quote.last_price > 0 else None


def _spread_bps(quote: QuoteSnapshot, mid_price: float | None) -> float | None:
    if not mid_price or mid_price <= 0 or not quote.bid or not quote.ask:
        return None
    return ((quote.ask[0].price - quote.bid[0].price) / mid_price) * 10000.0


def _imbalance(quote: QuoteSnapshot) -> float | None:
    if not quote.bid or not quote.ask:
        return None
    bid_volume = _sum_volume(quote.bid[:5])
    ask_volume = _sum_volume(quote.ask[:5])
    total = bid_volume + ask_volume
    if total <= 0:
        return None
    return (bid_volume - ask_volume) / total


def _position_pnl_pct(position: PositionSnapshot | None, last_price: float) -> float | None:
    if position is None or position.cost_basis is None or position.cost_basis <= 0:
        return None
    return (last_price - position.cost_basis) / position.cost_basis


class RealtimeSignalEngine:
    def __init__(self, config: SignalConfig):
        self.config = config
        self.state_by_symbol: dict[str, SymbolState] = {}

    def _state(self, symbol: str) -> SymbolState:
        state = self.state_by_symbol.get(symbol)
        if state is None:
            state = SymbolState(window_size=self.config.window_size)
            self.state_by_symbol[symbol] = state
        return state

    def process(
        self,
        quote: QuoteSnapshot,
        position: PositionSnapshot | None,
        now_epoch: float | None = None,
    ) -> SignalDecision:
        now_epoch = now_epoch or time.time()
        state = self._state(quote.symbol)
        state.update(quote, now_epoch)

        momentum = state.momentum()
        mid_price = _mid_price(quote)
        spread_bps = _spread_bps(quote, mid_price)
        imbalance = _imbalance(quote)
        pnl_pct = _position_pnl_pct(position, quote.last_price)
        drawdown_pct = state.drawdown(quote.last_price)

        metrics = SignalMetrics(
            last_price=quote.last_price,
            mid_price=mid_price,
            spread_bps=spread_bps,
            imbalance=imbalance,
            momentum=momentum,
            pnl_pct=pnl_pct,
            drawdown_pct=drawdown_pct,
        )

        if now_epoch - state.last_signal_ts < self.config.cooldown_seconds:
            return SignalDecision("HOLD", 0.0, "cooldown", metrics)

        if position and position.available_quantity > 0:
            sell_decision = self._maybe_sell(position, metrics)
            if sell_decision is not None:
                state.last_signal_ts = now_epoch
                return sell_decision

        buy_decision = self._maybe_buy(position, metrics)
        if buy_decision is not None:
            state.last_signal_ts = now_epoch
            return buy_decision

        return SignalDecision("HOLD", 0.0, "no_edge", metrics)

    def _maybe_sell(
        self,
        position: PositionSnapshot,
        metrics: SignalMetrics,
    ) -> SignalDecision | None:
        if metrics.pnl_pct is not None and metrics.pnl_pct <= self.config.stop_loss_pct:
            return SignalDecision("SELL", 1.0, "stop_loss", metrics)

        if (
            metrics.pnl_pct is not None
            and metrics.pnl_pct >= self.config.take_profit_pct
            and metrics.imbalance is not None
            and metrics.imbalance < 0
        ):
            return SignalDecision("SELL", 0.9, "take_profit_with_negative_flow", metrics)

        if (
            metrics.drawdown_pct is not None
            and metrics.drawdown_pct <= self.config.trailing_drawdown_pct
            and metrics.pnl_pct is not None
            and metrics.pnl_pct > 0
        ):
            return SignalDecision("SELL", 0.85, "trailing_drawdown", metrics)

        return None

    def _maybe_buy(
        self,
        position: PositionSnapshot | None,
        metrics: SignalMetrics,
    ) -> SignalDecision | None:
        if position is not None and position.quantity > 0:
            return None
        if metrics.imbalance is None or metrics.momentum is None or metrics.spread_bps is None:
            return None
        if metrics.spread_bps > self.config.spread_limit_bps:
            return None
        if metrics.imbalance < self.config.imbalance_threshold:
            return None
        if metrics.momentum < self.config.momentum_threshold:
            return None

        raw_score = (metrics.imbalance * 0.6) + (metrics.momentum * 100.0 * 0.4)
        score = max(0.0, min(1.0, raw_score))
        if math.isfinite(score) and score > 0:
            return SignalDecision("BUY", score, "positive_flow_and_momentum", metrics)
        return None
