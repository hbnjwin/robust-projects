from __future__ import annotations

import ast
import json
import math
import sqlite3
import time
from collections import deque
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:
    psycopg2 = None
    Json = None


# Single-file defaults for the PTrade editor. Prefer putting real values in
# get_research_path()/live_config.json so credentials do not live in source.
INLINE_RUNTIME_CONFIG = {
    "strategy_name": "ptrade_tick_signal_v1",
    "watchlist": ["600570.SS"],
    "track_positions": True,
    "enable_trading": False,
    "enable_l2": True,
    "refresh_positions_seconds": 6,
    "journal_path": "data/runtime/ptrade_signals.sqlite3",
    "postgres": {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 5432,
        "database": "quant",
        "user": "postgres",
        "password": "",
        "connect_timeout_seconds": 3,
        "account_id": "ptrade",
        "source": "ptrade",
        "watchlist_table_priority": ["watchlist_ptrade", "watchlist"],
        "positions_table": "ptrade_positions",
        "tick_table": "tick_ptrade_raw",
        "write_watchlist": True,
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


def _logger():
    try:
        return log.info
    except Exception:
        return print


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _runtime_root() -> Path:
    file_path = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
    candidates = [
        file_path.parent.parent if file_path.parent.name == "strategies" else file_path.parent,
        file_path.parent,
        Path.cwd(),
    ]
    try:
        research_root = get_research_path()
        if research_root:
            candidates.append(Path(str(research_root)))
    except Exception:
        pass
    for candidate in candidates:
        if (candidate / "live_config.json").exists() or (candidate / "config").exists():
            return candidate
    return candidates[0]


def _candidate_config_paths() -> list[Path]:
    root = _runtime_root()
    return [
        root / "live_config.json",
        root / "config" / "live_config.json",
        root / "ptrade-quant" / "config" / "live_config.json",
    ]


def _resolve_runtime_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return _runtime_root() / path


def _ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return
    except Exception:
        pass
    try:
        create_dir(str(path).replace("\\", "/"))
    except Exception:
        pass


def _load_external_config_payload() -> tuple[Path | None, dict[str, Any]]:
    for path in _candidate_config_paths():
        try:
            if path.exists():
                return path, json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            _logger()(f"config load skipped for {path}: {exc}")
    return None, {}


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
    write_watchlist: bool = True
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
    journal_path: str
    signal: SignalConfig
    postgres: PostgresConfig


def load_runtime_config() -> RuntimeConfig:
    config_path, external_payload = _load_external_config_payload()
    payload = _deep_merge(INLINE_RUNTIME_CONFIG, external_payload)
    signal = SignalConfig(**payload.get("signal", {}))
    postgres = PostgresConfig(**payload.get("postgres", {}))
    watchlist = sorted(
        {
            normalize_symbol(symbol)
            for symbol in payload.get("watchlist", [])
            if isinstance(symbol, str) and symbol.strip()
        }
    )
    if config_path is not None:
        _logger()(f"loaded external config: {config_path}")
    else:
        _logger()("external config not found, using inline defaults")
    return RuntimeConfig(
        strategy_name=payload.get("strategy_name", "ptrade_tick_signal_v1"),
        watchlist=watchlist,
        track_positions=bool(payload.get("track_positions", True)),
        enable_trading=bool(payload.get("enable_trading", False)),
        enable_l2=bool(payload.get("enable_l2", True)),
        refresh_positions_seconds=int(payload.get("refresh_positions_seconds", 6)),
        journal_path=payload.get("journal_path", "data/runtime/ptrade_signals.sqlite3"),
        signal=signal,
        postgres=postgres,
    )


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

    bid = _parse_levels(_find_first(tick_data, "bid", "bid_grp", "bids", "bid_group"))
    ask = _parse_levels(_find_first(tick_data, "ask", "ask_grp", "asks", "ask_group", "offer_grp"))
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
        symbol=normalize_symbol(symbol),
        quantity=_safe_int(_find_first(root, "amount", "quantity", "current_amount")),
        available_quantity=_safe_int(_find_first(root, "enable_amount", "available_quantity", "enable_qty")),
        cost_basis=_safe_float(_find_first(root, "cost_basis", "avg_cost", "cost_price")),
        last_price=_safe_float(_find_first(root, "last_sale_price", "last_price", "price")),
        update_time=str(update_time) if update_time is not None else None,
    )


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

    def process(
        self,
        quote: QuoteSnapshot,
        position: PositionSnapshot | None,
        now_epoch: float | None = None,
    ) -> SignalDecision:
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
            sell_decision = self._maybe_sell(position, metrics)
            if sell_decision is not None:
                state.last_signal_ts = now_epoch
                return sell_decision

        buy_decision = self._maybe_buy(position, metrics)
        if buy_decision is not None:
            state.last_signal_ts = now_epoch
            return buy_decision

        return SignalDecision("HOLD", 0.0, "no_edge", metrics)

    def _maybe_sell(self, position: PositionSnapshot, metrics: SignalMetrics) -> SignalDecision | None:
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


class SQLiteJournal:
    def __init__(self, path: Path):
        self.path = path
        _ensure_dir(self.path.parent)
        self.connection = sqlite3.connect(self.path)
        self._init_schema()

    def _init_schema(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tick_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                symbol TEXT NOT NULL,
                last_price REAL NOT NULL,
                spread_bps REAL,
                imbalance REAL,
                momentum REAL,
                raw_json TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                score REAL NOT NULL,
                reason TEXT NOT NULL,
                pnl_pct REAL,
                drawdown_pct REAL,
                position_qty INTEGER,
                suggested_shares INTEGER
            )
            """
        )
        self.connection.commit()

    def record_tick(self, quote: QuoteSnapshot, decision: SignalDecision) -> None:
        metrics = decision.metrics
        self.connection.execute(
            """
            INSERT INTO tick_snapshots (
                ts, symbol, last_price, spread_bps, imbalance, momentum, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.timestamp,
                quote.symbol,
                quote.last_price,
                metrics.spread_bps,
                metrics.imbalance,
                metrics.momentum,
                json.dumps(quote.raw, ensure_ascii=False, default=str),
            ),
        )
        self.connection.commit()

    def record_signal(
        self,
        quote: QuoteSnapshot,
        decision: SignalDecision,
        position: PositionSnapshot | None,
    ) -> None:
        metrics = decision.metrics
        self.connection.execute(
            """
            INSERT INTO signal_events (
                ts, symbol, action, score, reason, pnl_pct, drawdown_pct, position_qty, suggested_shares
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.timestamp,
                quote.symbol,
                decision.action,
                decision.score,
                decision.reason,
                metrics.pnl_pct,
                metrics.drawdown_pct,
                position.quantity if position else 0,
                decision.suggested_shares,
            ),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return _json_ready(value.to_dict(orient="records"))
        except TypeError:
            return _json_ready(value.to_dict())
        except Exception:
            pass
    if hasattr(value, "tolist") and callable(value.tolist):
        try:
            return _json_ready(value.tolist())
        except Exception:
            pass
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
                account_id,
                strategy_name,
                symbol,
                quantity,
                available_quantity,
                cost_basis,
                last_price,
                source_update_time,
                raw_json,
                updated_at
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

    def insert_tick_raw(
        self,
        strategy_name: str,
        quote: QuoteSnapshot,
        decision: SignalDecision,
        capture: dict[str, Any] | None = None,
    ) -> None:
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
                account_id,
                strategy_name,
                source,
                trade_date,
                symbol,
                quote_time_text,
                last_price,
                open_price,
                high_price,
                low_price,
                pre_close,
                volume,
                turnover,
                bid1_price,
                bid1_volume,
                ask1_price,
                ask1_volume,
                quote_source,
                has_l2,
                bid_level_count,
                ask_level_count,
                spread_bps,
                imbalance,
                momentum,
                entrust_count,
                transaction_count,
                action,
                score,
                tick_payload_json,
                entrust_payload_json,
                transaction_payload_json,
                raw_json,
                created_at
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
    raw_positions = {}
    try:
        raw_positions = get_positions()
    except Exception as exc:
        _logger()(f"get_positions failed: {exc}")
        return

    normalized: dict[str, PositionSnapshot] = {}
    if isinstance(raw_positions, dict):
        for symbol, payload in raw_positions.items():
            position = normalize_position(symbol, payload)
            if position and position.quantity > 0:
                normalized[position.symbol] = position
    g.positions = normalized
    if g.pg_store is not None:
        try:
            g.pg_store.upsert_positions(g.config.strategy_name, normalized)
        except Exception as exc:
            _logger()(f"postgres positions sync skipped: {exc}")
    if g.config.track_positions:
        merged = sorted(set(g.config.watchlist) | set(normalized))
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


def _pick_active_symbols() -> list[str]:
    if not g.config.track_positions:
        return list(g.config.watchlist)
    return sorted(set(g.config.watchlist) | set(g.positions))


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _capture_tick_sample_once(symbol: str, capture: dict[str, object], quote: QuoteSnapshot) -> None:
    if symbol in g.sampled_symbols:
        return
    g.sampled_symbols.add(symbol)

    payload = {
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "quote_source": capture.get("quote_source"),
        "tick_payload": capture.get("tick_payload"),
        "entrust_payload": capture.get("entrust_payload"),
        "transaction_payload": capture.get("transaction_payload"),
        "normalized_quote": asdict(quote),
    }
    file_name = f"{time.strftime('%Y%m%d')}_{symbol.replace('.', '_')}.json"
    sample_path = g.tick_sample_dir / file_name
    _ensure_dir(sample_path.parent)
    sample_path.write_text(_safe_json(payload), encoding="utf-8")
    _logger()(f"tick_sample_saved[{symbol}]={sample_path}")


def _fetch_orderflow_payload(api_name: str, symbol: str, data_count: int):
    try:
        api_func = globals().get(api_name)
        if api_func is None:
            return None
        return api_func([symbol], data_count=data_count, start_pos=0, search_direction=1)
    except Exception as exc:
        _logger()(f"{api_name} failed for {symbol}: {exc}")
        return None


def _build_tick_capture(symbol: str, raw_tick_payload, quote: QuoteSnapshot) -> dict[str, object]:
    quote_source = "tick_data" if raw_tick_payload is not None else "snapshot_fallback"
    capture = {
        "quote_source": quote_source,
        "tick_payload": raw_tick_payload if raw_tick_payload is not None else quote.raw,
    }
    if g.pg_store is None:
        return capture

    refresh_seconds = max(3, g.config.postgres.microstructure_refresh_seconds)
    cache_entry = g.microstructure_cache.get(symbol, {})
    fetched_at = float(cache_entry.get("fetched_at", 0.0))
    now = time.time()
    if now - fetched_at >= refresh_seconds:
        entrust_payload = None
        transaction_payload = None
        if g.config.postgres.capture_entrust:
            entrust_payload = _fetch_orderflow_payload(
                "get_individual_entrust",
                symbol,
                g.config.postgres.entrust_data_count,
            )
        if g.config.postgres.capture_transaction:
            transaction_payload = _fetch_orderflow_payload(
                "get_individual_transaction",
                symbol,
                g.config.postgres.transaction_data_count,
            )
        cache_entry = {
            "fetched_at": now,
            "entrust_payload": entrust_payload,
            "transaction_payload": transaction_payload,
        }
        g.microstructure_cache[symbol] = cache_entry

    capture["entrust_payload"] = cache_entry.get("entrust_payload")
    capture["transaction_payload"] = cache_entry.get("transaction_payload")
    return capture


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
    quote = _resolve_quote_for_cycle(symbol, raw_payload, prefer_snapshot=prefer_snapshot)
    if quote is None:
        return

    position = g.positions.get(symbol)
    decision = g.engine.process(quote=quote, position=position, now_epoch=now_epoch)
    g.journal.record_tick(quote, decision)
    capture = _build_tick_capture(symbol, raw_payload, quote)
    _capture_tick_sample_once(symbol, capture, quote)
    if g.pg_store is not None:
        try:
            g.pg_store.insert_tick_raw(g.config.strategy_name, quote, decision, capture=capture)
        except Exception as exc:
            _logger()(f"postgres tick sync skipped for {symbol}: {exc}")
    if decision.action != "HOLD":
        g.journal.record_signal(quote, decision, position)
    _maybe_execute(context, quote, position, decision)


def _round_to_lot(shares: int, lot_size: int) -> int:
    if shares <= 0:
        return 0
    return (shares // lot_size) * lot_size


def _suggest_buy_shares(context, quote: QuoteSnapshot) -> int:
    cash = getattr(context.portfolio, "cash", 0.0)
    budget = float(cash) * g.config.signal.max_position_ratio
    shares = int(budget / max(quote.last_price, 0.01))
    shares = min(shares, g.config.signal.max_single_order_shares)
    return _round_to_lot(shares, g.config.signal.lot_size)


def _maybe_execute(context, quote: QuoteSnapshot, position: PositionSnapshot | None, decision: SignalDecision) -> None:
    if decision.action == "HOLD":
        return

    if decision.action == "BUY":
        shares = _suggest_buy_shares(context, quote)
        decision.suggested_shares = shares
        if shares <= 0:
            _logger()(f"[{quote.symbol}] BUY skipped: insufficient cash")
            return
        if not g.config.enable_trading:
            _logger()(f"[{quote.symbol}] BUY recommendation: shares={shares}, reason={decision.reason}")
            return
        order_tick(quote.symbol, shares, g.config.signal.buy_price_gear)
        _logger()(f"[{quote.symbol}] BUY executed: shares={shares}, reason={decision.reason}")
        return

    if decision.action == "SELL":
        sellable = position.available_quantity if position else 0
        shares = min(sellable, g.config.signal.max_single_order_shares)
        shares = _round_to_lot(shares, g.config.signal.lot_size)
        decision.suggested_shares = shares
        if shares <= 0:
            _logger()(f"[{quote.symbol}] SELL skipped: no sellable position")
            return
        if not g.config.enable_trading:
            _logger()(f"[{quote.symbol}] SELL recommendation: shares={shares}, reason={decision.reason}")
            return
        order_tick(quote.symbol, -shares, g.config.signal.sell_price_gear)
        _logger()(f"[{quote.symbol}] SELL executed: shares={shares}, reason={decision.reason}")


def initialize(context):
    g.runtime_root = _runtime_root()
    g.config = load_runtime_config()
    g.pg_store = None
    if g.config.postgres.enabled:
        try:
            g.pg_store = PostgresRuntimeStore(g.config.postgres)
            table_name, watchlist = g.pg_store.load_watchlist()
            if watchlist:
                g.config.watchlist = watchlist
                _logger()(f"loaded watchlist from postgres table={table_name}, count={len(watchlist)}")
            else:
                _logger()("postgres watchlist unavailable, using config fallback")
        except Exception as exc:
            _logger()(f"postgres bootstrap skipped: {exc}")
            g.pg_store = None

    g.engine = RealtimeSignalEngine(g.config.signal)
    g.positions = {}
    g.microstructure_cache = {}
    g.sampled_symbols = set()
    g.tick_sample_dir = g.runtime_root / "data" / "runtime" / "tick_samples"
    g.universe = list(g.config.watchlist)
    g.last_position_refresh = 0.0
    journal_path = _resolve_runtime_path(g.config.journal_path)
    g.journal = SQLiteJournal(journal_path)
    set_universe(g.universe)
    _safe_set_parameters(g.config.enable_l2)
    _logger()(f"initialized strategy={g.config.strategy_name}, runtime_root={g.runtime_root}, watchlist={g.universe}")


def before_trading_start(context, data):
    _refresh_positions()
    _logger()(f"before_trading_start positions={sorted(g.positions)}")


def handle_data(context, data):
    now = time.time()
    if now - g.last_position_refresh >= g.config.refresh_positions_seconds:
        _refresh_positions()

    for symbol in _pick_active_symbols():
        raw_payload = data.get(symbol) if isinstance(data, dict) else None
        _process_symbol_cycle(context, symbol, raw_payload, now_epoch=now, prefer_snapshot=True)


def tick_data(context, data):
    now = time.time()
    if now - g.last_position_refresh >= g.config.refresh_positions_seconds:
        _refresh_positions()

    for symbol in _pick_active_symbols():
        raw_tick_payload = data.get(symbol) if isinstance(data, dict) else None
        _process_symbol_cycle(context, symbol, raw_tick_payload, now_epoch=now, prefer_snapshot=False)


def on_order_response(context, response):
    _logger()(f"order_response: {response}")


def on_trade_response(context, response):
    _logger()(f"trade_response: {response}")


def after_trading_end(context, data):
    try:
        g.journal.close()
    except Exception:
        pass
    try:
        if g.pg_store is not None:
            g.pg_store.close()
    except Exception:
        pass
