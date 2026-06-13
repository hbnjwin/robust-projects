from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from typing import Any

from .models import Level, PositionSnapshot, QuoteSnapshot


NUMERIC_FIELDS = (
    "last_price",
    "price",
    "match",
    "new_price",
    "close",
)


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _coerce_structure(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text[0] in "[{(":
            try:
                return ast.literal_eval(text)
            except (SyntaxError, ValueError):
                return value
    return value


def _find_first(mapping: Mapping[str, Any], *candidates: str) -> Any:
    for candidate in candidates:
        if candidate in mapping:
            return mapping[candidate]
    return None


def _parse_levels(raw_value: Any) -> list[Level]:
    payload = _coerce_structure(raw_value)
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        levels: list[Level] = []
        for item in payload:
            parsed = _coerce_structure(item)
            if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
                if parsed and isinstance(parsed[0], Sequence) and not isinstance(
                    parsed[0], (str, bytes, bytearray)
                ):
                    for nested in parsed:
                        level = _parse_level(_coerce_structure(nested))
                        if level is not None:
                            levels.append(level)
                    continue
            level = _parse_level(parsed)
            if level is not None:
                levels.append(level)
        return levels
    return []


def _parse_level(payload: Any) -> Level | None:
    if isinstance(payload, Mapping):
        price = _safe_float(_find_first(payload, "price", "px", "p"))
        volume = _safe_float(_find_first(payload, "volume", "vol", "qty", "v"))
        if price and volume is not None:
            return Level(price=price, volume=volume)
        return None
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        numeric_values = [_safe_float(item) for item in payload]
        numeric_values = [value for value in numeric_values if value is not None]
        if len(numeric_values) >= 2:
            return Level(price=numeric_values[0], volume=numeric_values[1])
    return None


def normalize_quote(symbol: str, payload: Any) -> QuoteSnapshot | None:
    root = _coerce_structure(payload)
    if isinstance(root, Mapping) and symbol in root and isinstance(root[symbol], Mapping):
        root = root[symbol]
    if not isinstance(root, Mapping):
        return None

    tick_data = root.get("tick", root)
    if not isinstance(tick_data, Mapping):
        tick_data = root

    last_price = None
    for field in NUMERIC_FIELDS:
        last_price = _safe_float(tick_data.get(field))
        if last_price is not None:
            break
    if last_price is None:
        return None

    bid = _parse_levels(_find_first(tick_data, "bid", "bid_grp", "bids", "bid_group"))
    ask = _parse_levels(_find_first(tick_data, "ask", "ask_grp", "asks", "ask_group"))

    time_value = _find_first(tick_data, "timestamp", "time", "datetime", "update_time")
    return QuoteSnapshot(
        symbol=symbol,
        timestamp=str(time_value) if time_value is not None else None,
        last_price=last_price,
        open_price=_safe_float(_find_first(tick_data, "open", "open_price")),
        high_price=_safe_float(_find_first(tick_data, "high", "high_price")),
        low_price=_safe_float(_find_first(tick_data, "low", "low_price")),
        pre_close=_safe_float(_find_first(tick_data, "pre_close", "preclose", "yes_close")),
        volume=_safe_float(_find_first(tick_data, "volume", "vol")),
        turnover=_safe_float(_find_first(tick_data, "turnover", "amount", "money")),
        bid=bid,
        ask=ask,
        raw=dict(root),
    )


def normalize_position(symbol: str, payload: Any) -> PositionSnapshot | None:
    root = _coerce_structure(payload)
    if isinstance(root, Mapping) and symbol in root and isinstance(root[symbol], Mapping):
        root = root[symbol]
    if not isinstance(root, Mapping):
        return None

    update_time = _find_first(root, "update_time")
    return PositionSnapshot(
        symbol=symbol,
        quantity=_safe_int(_find_first(root, "amount", "quantity")),
        available_quantity=_safe_int(_find_first(root, "enable_amount", "available_quantity")),
        cost_basis=_safe_float(_find_first(root, "cost_basis", "avg_cost")),
        last_price=_safe_float(_find_first(root, "last_sale_price", "last_price", "price")),
        update_time=str(update_time) if update_time is not None else None,
    )
