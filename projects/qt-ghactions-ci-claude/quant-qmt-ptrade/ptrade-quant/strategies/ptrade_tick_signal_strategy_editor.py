from __future__ import annotations

import ast
import json
import math
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:
    psycopg2 = None
    Json = None


# Edit only this block when pasting into the PTrade editor.
INLINE_RUNTIME_CONFIG = {
    "strategy_name": "ptrade_tick_signal_editor_v1",
    "watchlist": ["600570.SS"],
    "track_positions": True,
    "enable_trading": False,
    "enable_l2": True,
    "refresh_positions_seconds": 6,
    "postgres": {
        "enabled": False,
        "host": "192.168.68.229",
        "port": 5432,
        "database": "quant",
        "user": "postgres",
        "password": "limit123",
        "connect_timeout_seconds": 3,
        "account_id": "ptrade",
        "source": "ptrade",
        "watchlist_table_priority": ["watchlist_ptrade", "watchlist"],
        "positions_table": "ptrade_positions",
        "tick_table": "tick_ptrade_raw",
        "write_positions": True,
        "write_ticks": True,
        "capture_entrust": True,
        "capture_transaction": True,
        "microstructure_refresh_seconds": 15,
        "entrust_data_count": 20,
        "transaction_data_count": 20,
    },
    "signal": {
        "window_size": 24,
        "imbalance_threshold": 0.16,
        "momentum_threshold": 0.003,
        "spread_limit_bps": 18.0,
        "stop_loss_pct": -0.02,
        "take_profit_pct": 0.04,
        "trailing_drawdown_pct": -0.012,
        "cooldown_seconds": 30,
        "max_position_ratio": 0.2,
        "max_single_order_shares": 1000,
        "lot_size": 100,
        "buy_price_gear": "1",
        "sell_price_gear": "-1",
    },
}

NUMERIC_FIELDS = ("last_price", "price", "match", "new_price", "close", "last_px")
SignalAction = Literal["BUY", "SELL", "HOLD"]


_MODULE_CONFIG = None
_MODULE_ENGINE = None
_MODULE_PG_STORE = None
_MODULE_MICROSTRUCTURE_CACHE: dict[str, dict[str, Any]] = {}
_MODULE_SAMPLED_SYMBOLS: set[str] = set()


def _logger():
    try:
        return log.info
    except Exception:
        return print


def normalize_symbol(symbol: str) -> str:
    text = str(symbol).strip().upper()
    if "." not in text:
        return text
    code, market = text.rsplit(".", 1)
    market_map = {
        "SH": "SS",
        "XSHG": "SS",
        "SZ": "SZ",
        "XSHE": "SZ",
        "BJ": "BJ",
        "BSE": "BJ",
    }
    return f"{code}.{market_map.get(market, market)}"


@dataclass(slots=True)
class SignalConfig:
    window_size: int = 24
    imbalance_threshold: float = 0.16
    momentum_threshold: float = 0.003
    spread_limit_bps: float = 18.0
    stop_loss_pct: float = -0.02
    take_profit_pct: float = 0.04
    trailing_drawdown_pct: float = -0.012
    cooldown_seconds: int = 30
    max_position_ratio: float = 0.2
    max_single_order_shares: int = 1000
    lot_size: int = 100
    buy_price_gear: str = "1"
    sell_price_gear: str = "-1"


@dataclass(slots=True)
class PostgresConfig:
    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "quant"
    user: str = "postgres"
    password: str = ""
    connect_timeout_seconds: int = 3
    account_id: str = "ptrade"
    source: str = "ptrade"
    watchlist_table_priority: list[str] | None = None
    positions_table: str = "ptrade_positions"
    tick_table: str = "tick_ptrade_raw"
    write_positions: bool = True
    write_ticks: bool = True
    capture_entrust: bool = True
    capture_transaction: bool = True
    microstructure_refresh_seconds: int = 15
    entrust_data_count: int = 20
    transaction_data_count: int = 20

    def __post_init__(self) -> None:
        if self.watchlist_table_priority is None:
            self.watchlist_table_priority = ["watchlist_ptrade", "watchlist"]


@dataclass(slots=True)
class RuntimeConfig:
    strategy_name: str
    watchlist: list[str]
    track_positions: bool
    enable_trading: bool
    enable_l2: bool
    refresh_positions_seconds: int
    signal: SignalConfig
    postgres: PostgresConfig


def load_runtime_config() -> RuntimeConfig:
    payload = INLINE_RUNTIME_CONFIG
    watchlist = sorted(
        {
            normalize_symbol(symbol)
            for symbol in payload.get("watchlist", [])
            if isinstance(symbol, str) and symbol.strip()
        }
    )
    return RuntimeConfig(
        strategy_name=payload.get("strategy_name", "ptrade_tick_signal_editor_v1"),
        watchlist=watchlist,
        track_positions=bool(payload.get("track_positions", True)),
        enable_trading=bool(payload.get("enable_trading", False)),
        enable_l2=bool(payload.get("enable_l2", True)),
        refresh_positions_seconds=int(payload.get("refresh_positions_seconds", 6)),
        signal=SignalConfig(**payload.get("signal", {})),
        postgres=PostgresConfig(**payload.get("postgres", {})),
    )


def _config() -> RuntimeConfig:
    if _MODULE_CONFIG is None:
        raise RuntimeError("runtime config is not initialized")
    return _MODULE_CONFIG


def _engine() -> "RealtimeSignalEngine":
    if _MODULE_ENGINE is None:
        raise RuntimeError("signal engine is not initialized")
    return _MODULE_ENGINE


def _pg_store() -> "PostgresRuntimeStore | None":
    return _MODULE_PG_STORE


def _position_from_store(symbol: str) -> "PositionSnapshot | None":
    raw_position = g.positions.get(symbol)
    if isinstance(raw_position, Mapping):
        return normalize_position(symbol, raw_position)
    return None


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


def _parse_levels(raw_value: Any) -> list[Level]:
    payload = _coerce_structure(raw_value)
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        return []
    levels: list[Level] = []
    for item in payload:
        parsed = _coerce_structure(item)
        if isinstance(parsed, Sequence) and not isinstance(parsed, (str, bytes, bytearray)):
            if parsed and isinstance(parsed[0], Sequence) and not isinstance(parsed[0], (str, bytes, bytearray)):
                for nested in parsed:
                    level = _parse_level(_coerce_structure(nested))
                    if level is not None:
                        levels.append(level)
                continue
        level = _parse_level(parsed)
        if level is not None:
            levels.append(level)
    return levels


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
    for field_name in NUMERIC_FIELDS:
        last_price = _safe_float(tick_data.get(field_name))
        if last_price is not None:
            break
    if last_price is None:
        return None

    time_value = _find_first(tick_data, "timestamp", "time", "datetime", "update_time", "hsTimeStamp")
    return QuoteSnapshot(
        symbol=normalize_symbol(symbol),
        timestamp=str(time_value) if time_value is not None else None,
        last_price=last_price,
        open_price=_safe_float(_find_first(tick_data, "open", "open_price", "open_px")),
        high_price=_safe_float(_find_first(tick_data, "high", "high_price", "high_px")),
        low_price=_safe_float(_find_first(tick_data, "low", "low_price", "low_px")),
        pre_close=_safe_float(_find_first(tick_data, "pre_close", "preclose", "yes_close", "preclose_px")),
        volume=_safe_float(_find_first(tick_data, "volume", "vol", "business_amount")),
        turnover=_safe_float(_find_first(tick_data, "turnover", "amount", "money", "business_balance")),
        bid=_parse_levels(_find_first(tick_data, "bid", "bid_grp", "bids", "bid_group")),
        ask=_parse_levels(_find_first(tick_data, "ask", "ask_grp", "asks", "ask_group", "offer_grp")),
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
        symbol=normalize_symbol(symbol),
        quantity=_safe_int(_find_first(root, "amount", "quantity", "current_amount")),
        available_quantity=_safe_int(_find_first(root, "enable_amount", "available_quantity", "enable_qty")),
        cost_basis=_safe_float(_find_first(root, "cost_basis", "avg_cost", "cost_price")),
        last_price=_safe_float(_find_first(root, "last_sale_price", "last_price", "price")),
        update_time=str(update_time) if update_time is not None else None,
    )


def _sum_volume(levels: list[Level]) -> float:
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

    def process(self, quote: QuoteSnapshot, position: PositionSnapshot | None, now_epoch: float | None = None) -> SignalDecision:
        now_epoch = now_epoch or time.time()
        state = self._state(quote.symbol)
        state.update(quote, now_epoch)

        metrics = SignalMetrics(
            last_price=quote.last_price,
            mid_price=_mid_price(quote),
            spread_bps=None,
            imbalance=_imbalance(quote),
            momentum=state.momentum(),
            pnl_pct=_position_pnl_pct(position, quote.last_price),
            drawdown_pct=state.drawdown(quote.last_price),
        )
        metrics.spread_bps = _spread_bps(quote, metrics.mid_price)

        if now_epoch - state.last_signal_ts < self.config.cooldown_seconds:
            return SignalDecision("HOLD", 0.0, "cooldown", metrics)
        if position and position.available_quantity > 0:
            sell_decision = self._maybe_sell(metrics)
            if sell_decision is not None:
                state.last_signal_ts = now_epoch
                return sell_decision
        buy_decision = self._maybe_buy(position, metrics)
        if buy_decision is not None:
            state.last_signal_ts = now_epoch
            return buy_decision
        return SignalDecision("HOLD", 0.0, "no_edge", metrics)

    def _maybe_sell(self, metrics: SignalMetrics) -> SignalDecision | None:
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

    def _maybe_buy(self, position: PositionSnapshot | None, metrics: SignalMetrics) -> SignalDecision | None:
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


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    return str(value)


def _payload_count(payload: Any, symbol: str | None = None) -> int:
    resolved = payload
    if symbol and isinstance(payload, Mapping) and symbol in payload:
        resolved = payload[symbol]
    if resolved is None:
        return 0
    if isinstance(resolved, Sequence) and not isinstance(resolved, (str, bytes, bytearray)):
        return len(resolved)
    if hasattr(resolved, "__len__"):
        try:
            return len(resolved)
        except Exception:
            return 1
    return 1


def _top_of_book(levels: list[Any]) -> tuple[float | None, float | None]:
    if not levels:
        return None, None
    first = levels[0]
    return getattr(first, "price", None), getattr(first, "volume", None)


class PostgresRuntimeStore:
    def __init__(self, config: PostgresConfig):
        if psycopg2 is None or Json is None:
            raise RuntimeError("psycopg2 is not available")
        self.config = config
        self.connection = psycopg2.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.user,
            password=config.password,
            connect_timeout=config.connect_timeout_seconds,
        )
        self.connection.autocommit = True
        self._resolved_watchlist_table: str | None = None

    def close(self) -> None:
        self.connection.close()

    def _table_exists(self, table_name: str) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                select exists (
                    select 1
                    from information_schema.tables
                    where table_schema = 'public' and table_name = %s
                )
                """,
                (table_name,),
            )
            row = cursor.fetchone()
        return bool(row and row[0])

    def resolve_watchlist_table(self) -> str | None:
        if self._resolved_watchlist_table is not None:
            return self._resolved_watchlist_table
        for table_name in self.config.watchlist_table_priority or []:
            if self._table_exists(table_name):
                self._resolved_watchlist_table = table_name
                return table_name
        return None

    def load_watchlist(self) -> tuple[str | None, list[str]]:
        table_name = self.resolve_watchlist_table()
        if table_name is None:
            return None, []
        with self.connection.cursor() as cursor:
            cursor.execute(f"select ts_code from public.{table_name} where ts_code is not null order by ts_code")
            rows = cursor.fetchall()
        watchlist = sorted({normalize_symbol(row[0]) for row in rows if row and row[0]})
        return table_name, watchlist

    def upsert_positions(self, strategy_name: str, positions: dict[str, PositionSnapshot]) -> None:
        if not self.config.write_positions or not positions:
            return
        sql = f"""
            insert into public.{self.config.positions_table} (
                account_id, strategy_name, symbol, quantity, available_quantity,
                cost_basis, last_price, source_update_time, raw_json, updated_at
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            on conflict (account_id, strategy_name, symbol) do update set
                quantity = excluded.quantity,
                available_quantity = excluded.available_quantity,
                cost_basis = excluded.cost_basis,
                last_price = excluded.last_price,
                source_update_time = excluded.source_update_time,
                raw_json = excluded.raw_json,
                updated_at = now()
        """
        with self.connection.cursor() as cursor:
            for symbol, position in positions.items():
                cursor.execute(
                    sql,
                    (
                        self.config.account_id,
                        strategy_name,
                        normalize_symbol(symbol),
                        position.quantity,
                        position.available_quantity,
                        position.cost_basis,
                        position.last_price,
                        position.update_time,
                        Json(asdict(position)),
                    ),
                )

    def insert_tick_raw(self, strategy_name: str, quote: QuoteSnapshot, decision: SignalDecision, capture: dict[str, Any] | None = None) -> None:
        if not self.config.write_ticks:
            return
        capture = capture or {}
        metrics = decision.metrics
        bid1_price, bid1_volume = _top_of_book(quote.bid)
        ask1_price, ask1_volume = _top_of_book(quote.ask)
        tick_payload = _json_ready(capture.get("tick_payload", quote.raw))
        entrust_payload = _json_ready(capture.get("entrust_payload"))
        transaction_payload = _json_ready(capture.get("transaction_payload"))
        quote_source = str(capture.get("quote_source", "tick_data"))
        has_l2 = bool(quote.bid or quote.ask)
        sql = f"""
            insert into public.{self.config.tick_table} (
                account_id, strategy_name, source, trade_date, symbol, quote_time_text,
                last_price, open_price, high_price, low_price, pre_close, volume, turnover,
                bid1_price, bid1_volume, ask1_price, ask1_volume, quote_source, has_l2,
                bid_level_count, ask_level_count, spread_bps, imbalance, momentum,
                entrust_count, transaction_count, action, score, tick_payload_json,
                entrust_payload_json, transaction_payload_json, raw_json, created_at
            ) values (
                %s, %s, %s, current_date, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, now()
            )
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    self.config.account_id,
                    strategy_name,
                    self.config.source,
                    normalize_symbol(quote.symbol),
                    quote.timestamp,
                    quote.last_price,
                    quote.open_price,
                    quote.high_price,
                    quote.low_price,
                    quote.pre_close,
                    quote.volume,
                    quote.turnover,
                    bid1_price,
                    bid1_volume,
                    ask1_price,
                    ask1_volume,
                    quote_source,
                    has_l2,
                    len(quote.bid),
                    len(quote.ask),
                    metrics.spread_bps,
                    metrics.imbalance,
                    metrics.momentum,
                    _payload_count(entrust_payload, quote.symbol),
                    _payload_count(transaction_payload, quote.symbol),
                    decision.action,
                    decision.score,
                    Json(tick_payload),
                    Json(entrust_payload),
                    Json(transaction_payload),
                    Json(
                        {
                            "quote": asdict(quote),
                            "decision": asdict(decision),
                            "quote_source": quote_source,
                            "has_l2": has_l2,
                            "captured_at": datetime.now().isoformat(),
                        }
                    ),
                ),
            )


def _safe_set_parameters(enable_l2: bool) -> None:
    try:
        set_parameters(
            holiday_not_do_before="1",
            tick_data_no_l2="0" if enable_l2 else "1",
            receive_other_response="1",
            receive_cancel_response="1",
        )
    except Exception as exc:
        _logger()(f"set_parameters skipped: {exc}")


def _refresh_positions() -> None:
    cfg = _config()
    pg_store = _pg_store()
    raw_positions = {}
    try:
        raw_positions = get_positions()
    except Exception as exc:
        _logger()(f"get_positions failed: {exc}")
        return
    normalized: dict[str, PositionSnapshot] = {}
    serialized: dict[str, dict[str, Any]] = {}
    if isinstance(raw_positions, dict):
        for symbol, payload in raw_positions.items():
            position = normalize_position(symbol, payload)
            if position and position.quantity > 0:
                normalized[position.symbol] = position
                serialized[position.symbol] = asdict(position)
    g.positions = serialized
    if pg_store is not None:
        try:
            pg_store.upsert_positions(cfg.strategy_name, normalized)
        except Exception as exc:
            _logger()(f"postgres positions sync skipped: {exc}")
    if cfg.track_positions:
        merged = sorted(set(cfg.watchlist) | set(normalized))
        g.universe = merged
        try:
            set_universe(merged)
        except Exception as exc:
            _logger()(f"set_universe refresh skipped: {exc}")
    g.last_position_refresh = time.time()


def _snapshot_for_symbol(symbol: str) -> QuoteSnapshot | None:
    try:
        payload = get_snapshot(symbol)
    except Exception as exc:
        _logger()(f"get_snapshot failed for {symbol}: {exc}")
        return None
    return normalize_quote(symbol, payload)


def _fetch_orderflow_payload(api_name: str, symbol: str, data_count: int):
    try:
        api_func = globals().get(api_name)
        if api_func is None:
            return None
        return api_func([symbol], data_count=data_count, start_pos=0, search_direction=1)
    except Exception as exc:
        _logger()(f"{api_name} failed for {symbol}: {exc}")
        return None


def _build_tick_capture(symbol: str, raw_payload, quote: QuoteSnapshot) -> dict[str, object]:
    cfg = _config()
    pg_store = _pg_store()
    capture = {
        "quote_source": "tick_data" if raw_payload is not None else "snapshot_fallback",
        "tick_payload": raw_payload if raw_payload is not None else quote.raw,
    }
    if pg_store is None:
        return capture
    refresh_seconds = max(3, cfg.postgres.microstructure_refresh_seconds)
    cache_entry = _MODULE_MICROSTRUCTURE_CACHE.get(symbol, {})
    fetched_at = float(cache_entry.get("fetched_at", 0.0))
    now = time.time()
    if now - fetched_at >= refresh_seconds:
        entrust_payload = None
        transaction_payload = None
        if cfg.postgres.capture_entrust:
            entrust_payload = _fetch_orderflow_payload("get_individual_entrust", symbol, cfg.postgres.entrust_data_count)
        if cfg.postgres.capture_transaction:
            transaction_payload = _fetch_orderflow_payload(
                "get_individual_transaction", symbol, cfg.postgres.transaction_data_count
            )
        cache_entry = {
            "fetched_at": now,
            "entrust_payload": entrust_payload,
            "transaction_payload": transaction_payload,
        }
        _MODULE_MICROSTRUCTURE_CACHE[symbol] = cache_entry
    capture["entrust_payload"] = cache_entry.get("entrust_payload")
    capture["transaction_payload"] = cache_entry.get("transaction_payload")
    return capture


def _round_to_lot(shares: int, lot_size: int) -> int:
    if shares <= 0:
        return 0
    return (shares // lot_size) * lot_size


def _suggest_buy_shares(context, quote: QuoteSnapshot) -> int:
    cfg = _config()
    cash = getattr(context.portfolio, "cash", 0.0)
    budget = float(cash) * cfg.signal.max_position_ratio
    shares = int(budget / max(quote.last_price, 0.01))
    shares = min(shares, cfg.signal.max_single_order_shares)
    return _round_to_lot(shares, cfg.signal.lot_size)


def _log_first_sample_once(symbol: str, capture: dict[str, object], quote: QuoteSnapshot) -> None:
    if symbol in _MODULE_SAMPLED_SYMBOLS:
        return
    _MODULE_SAMPLED_SYMBOLS.add(symbol)
    payload = {
        "symbol": symbol,
        "quote_source": capture.get("quote_source"),
        "quote": asdict(quote),
        "tick_payload": capture.get("tick_payload"),
    }
    _logger()(f"first_quote_sample[{symbol}]={json.dumps(payload, ensure_ascii=False, default=str)[:1200]}")


def _maybe_execute(context, quote: QuoteSnapshot, position: PositionSnapshot | None, decision: SignalDecision) -> None:
    cfg = _config()
    if decision.action == "HOLD":
        return
    if decision.action == "BUY":
        shares = _suggest_buy_shares(context, quote)
        decision.suggested_shares = shares
        if shares <= 0:
            _logger()(f"[{quote.symbol}] BUY skipped: insufficient cash")
            return
        if not cfg.enable_trading:
            _logger()(f"[{quote.symbol}] BUY recommendation: shares={shares}, reason={decision.reason}")
            return
        order_tick(quote.symbol, shares, cfg.signal.buy_price_gear)
        _logger()(f"[{quote.symbol}] BUY executed: shares={shares}, reason={decision.reason}")
        return
    if decision.action == "SELL":
        sellable = position.available_quantity if position else 0
        shares = min(sellable, cfg.signal.max_single_order_shares)
        shares = _round_to_lot(shares, cfg.signal.lot_size)
        decision.suggested_shares = shares
        if shares <= 0:
            _logger()(f"[{quote.symbol}] SELL skipped: no sellable position")
            return
        if not cfg.enable_trading:
            _logger()(f"[{quote.symbol}] SELL recommendation: shares={shares}, reason={decision.reason}")
            return
        order_tick(quote.symbol, -shares, cfg.signal.sell_price_gear)
        _logger()(f"[{quote.symbol}] SELL executed: shares={shares}, reason={decision.reason}")


def _pick_active_symbols() -> list[str]:
    cfg = _config()
    if not cfg.track_positions:
        return list(cfg.watchlist)
    return sorted(set(cfg.watchlist) | set(g.positions))


def _resolve_quote_for_cycle(symbol: str, raw_payload, prefer_snapshot: bool) -> QuoteSnapshot | None:
    if prefer_snapshot:
        quote = _snapshot_for_symbol(symbol)
        if quote is not None:
            return quote
    quote = normalize_quote(symbol, raw_payload)
    if quote is not None:
        return quote
    if not prefer_snapshot:
        return _snapshot_for_symbol(symbol)
    return None


def _process_symbol_cycle(context, symbol: str, raw_payload, now_epoch: float, prefer_snapshot: bool) -> None:
    cfg = _config()
    engine = _engine()
    pg_store = _pg_store()
    quote = _resolve_quote_for_cycle(symbol, raw_payload, prefer_snapshot=prefer_snapshot)
    if quote is None:
        return
    position = _position_from_store(symbol)
    decision = engine.process(quote=quote, position=position, now_epoch=now_epoch)
    capture = _build_tick_capture(symbol, raw_payload, quote)
    _log_first_sample_once(symbol, capture, quote)
    if pg_store is not None:
        try:
            pg_store.insert_tick_raw(cfg.strategy_name, quote, decision, capture=capture)
        except Exception as exc:
            _logger()(f"postgres tick sync skipped for {symbol}: {exc}")
    _maybe_execute(context, quote, position, decision)


def initialize(context):
    global _MODULE_CONFIG, _MODULE_ENGINE, _MODULE_PG_STORE, _MODULE_MICROSTRUCTURE_CACHE, _MODULE_SAMPLED_SYMBOLS
    cfg = load_runtime_config()
    _MODULE_CONFIG = cfg
    _MODULE_PG_STORE = None
    if cfg.postgres.enabled:
        try:
            _MODULE_PG_STORE = PostgresRuntimeStore(cfg.postgres)
            table_name, watchlist = _MODULE_PG_STORE.load_watchlist()
            if watchlist:
                cfg.watchlist = watchlist
                _logger()(f"loaded watchlist from postgres table={table_name}, count={len(watchlist)}")
            else:
                _logger()("postgres watchlist unavailable, using inline watchlist")
        except Exception as exc:
            _logger()(f"postgres bootstrap skipped: {exc}")
            _MODULE_PG_STORE = None
    _MODULE_ENGINE = RealtimeSignalEngine(cfg.signal)
    _MODULE_MICROSTRUCTURE_CACHE = {}
    _MODULE_SAMPLED_SYMBOLS = set()
    g.positions = {}
    g.universe = list(cfg.watchlist)
    g.last_position_refresh = 0.0
    set_universe(g.universe)
    _safe_set_parameters(cfg.enable_l2)
    _logger()(f"initialized strategy={cfg.strategy_name}, watchlist={g.universe}")


def before_trading_start(context, data):
    _refresh_positions()
    _logger()(f"before_trading_start positions={sorted(g.positions)}")


def handle_data(context, data):
    cfg = _config()
    now = time.time()
    if now - g.last_position_refresh >= cfg.refresh_positions_seconds:
        _refresh_positions()
    for symbol in _pick_active_symbols():
        raw_payload = data.get(symbol) if isinstance(data, dict) else None
        _process_symbol_cycle(context, symbol, raw_payload, now_epoch=now, prefer_snapshot=True)


def tick_data(context, data):
    cfg = _config()
    now = time.time()
    if now - g.last_position_refresh >= cfg.refresh_positions_seconds:
        _refresh_positions()
    for symbol in _pick_active_symbols():
        raw_payload = data.get(symbol) if isinstance(data, dict) else None
        _process_symbol_cycle(context, symbol, raw_payload, now_epoch=now, prefer_snapshot=False)


def on_order_response(context, response):
    _logger()(f"order_response: {response}")


def on_trade_response(context, response):
    _logger()(f"trade_response: {response}")


def after_trading_end(context, data):
    try:
        if _MODULE_PG_STORE is not None:
            _MODULE_PG_STORE.close()
    except Exception:
        pass
