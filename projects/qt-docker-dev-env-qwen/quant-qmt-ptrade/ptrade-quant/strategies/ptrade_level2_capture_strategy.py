from __future__ import annotations

import ast
import json
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import Json
except Exception:
    psycopg2 = None
    Json = None


INLINE_RUNTIME_CONFIG = {
    "strategy_name": "ptrade_level2_capture_v1",
    "watchlist": ["600570.SS"],
    "enable_l2": True,
    "backtest_mode": False,
    "debug_logging": True,
    "log_interval_cycles": 20,
    "poll_interval_seconds": 3,
    "postgres": {
        "enabled": True,
        "host": "192.168.68.229",
        "port": 5432,
        "database": "quant",
        "user": "postgres",
        "password": "limit123",
        "connect_timeout_seconds": 3,
        "account_id": "ptrade",
        "source": "ptrade",
        "watchlist_table_priority": ["watchlist_ptrade", "watchlist"],
        "level2_table": "level2_ptrade_raw",
        "write_level2": True,
        "capture_entrust": True,
        "capture_transaction": True,
        "auto_create_tables": True,
        "entrust_data_count": 50,
        "transaction_data_count": 50,
        "dedupe_window": 4000,
    },
}

NUMERIC_FIELDS = ("last_price", "price", "match", "new_price", "close", "last_px")

_MODULE_CONFIG = None
_MODULE_PG_STORE = None
_MODULE_LAST_CAPTURE_AT: dict[str, float] = {}
_MODULE_CAPTURE_COUNTS: dict[str, int] = {}
_MODULE_SAMPLED_SYMBOLS: set[str] = set()
_MODULE_DAY_STAMP = ""
_MODULE_L2_DEDUPE_STATE: dict[str, dict[str, dict[str, Any]]] = {}


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
    market_map = {"SH": "SS", "XSHG": "SS", "SZ": "SZ", "XSHE": "SZ", "BJ": "BJ", "BSE": "BJ"}
    return f"{code}.{market_map.get(market, market)}"


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
    level2_table: str = "level2_ptrade_raw"
    write_level2: bool = True
    capture_entrust: bool = True
    capture_transaction: bool = True
    auto_create_tables: bool = True
    entrust_data_count: int = 50
    transaction_data_count: int = 50
    dedupe_window: int = 4000

    def __post_init__(self) -> None:
        if self.watchlist_table_priority is None:
            self.watchlist_table_priority = ["watchlist_ptrade", "watchlist"]


@dataclass(slots=True)
class RuntimeConfig:
    strategy_name: str
    watchlist: list[str]
    enable_l2: bool
    backtest_mode: bool
    debug_logging: bool
    log_interval_cycles: int
    poll_interval_seconds: int
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
        strategy_name=payload.get("strategy_name", "ptrade_level2_capture_v1"),
        watchlist=watchlist,
        enable_l2=bool(payload.get("enable_l2", True)),
        backtest_mode=bool(payload.get("backtest_mode", False)),
        debug_logging=bool(payload.get("debug_logging", True)),
        log_interval_cycles=max(1, int(payload.get("log_interval_cycles", 20))),
        poll_interval_seconds=max(1, int(payload.get("poll_interval_seconds", 3))),
        postgres=PostgresConfig(**payload.get("postgres", {})),
    )


def _config() -> RuntimeConfig:
    if _MODULE_CONFIG is None:
        raise RuntimeError("runtime config is not initialized")
    return _MODULE_CONFIG


def _pg_store() -> "PostgresRuntimeStore | None":
    return _MODULE_PG_STORE


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        values = [_safe_float(item) for item in payload]
        values = [value for value in values if value is not None]
        if len(values) >= 2:
            return Level(price=values[0], volume=values[1])
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
    normalized_symbol = normalize_symbol(symbol)
    if isinstance(root, Mapping):
        for candidate in (normalized_symbol, symbol):
            if candidate in root and isinstance(root[candidate], Mapping):
                root = root[candidate]
                break
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
        symbol=normalized_symbol,
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


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_ready(item) for item in value]
    return str(value)


def _top_of_book(levels: list[Level]) -> tuple[float | None, float | None]:
    if not levels:
        return None, None
    return levels[0].price, levels[0].volume


def _symbol_key_candidates(symbol: str) -> list[str]:
    normalized_symbol = normalize_symbol(symbol)
    return [normalized_symbol, symbol, normalized_symbol.split(".", 1)[0]]


def _extract_symbol_rows(payload: Any, symbol: str) -> tuple[list[str], list[list[Any]]]:
    root = _coerce_structure(payload)
    if not isinstance(root, Mapping):
        return [], []
    fields_raw = root.get("fields")
    fields = list(fields_raw) if isinstance(fields_raw, Sequence) and not isinstance(fields_raw, (str, bytes, bytearray)) else []
    symbol_rows = None
    for candidate in _symbol_key_candidates(symbol):
        if candidate in root:
            symbol_rows = root[candidate]
            break
    if not isinstance(symbol_rows, Sequence) or isinstance(symbol_rows, (str, bytes, bytearray)):
        return fields, []
    rows: list[list[Any]] = []
    for item in symbol_rows:
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            rows.append(list(item))
    return fields, rows


def _row_map(fields: list[str], row: Sequence[Any]) -> dict[str, Any]:
    if fields and len(fields) <= len(row):
        return {str(fields[index]): row[index] for index in range(len(fields))}
    return {}


def _entrust_row_key(fields: list[str], row: Sequence[Any]) -> tuple[Any, ...]:
    mapping = _row_map(fields, row)
    if mapping:
        return (
            mapping.get("business_time"),
            mapping.get("order_no"),
            mapping.get("business_direction"),
            mapping.get("business_amount"),
            mapping.get("hq_px"),
            mapping.get("trans_kind"),
        )
    return tuple(row)


def _transaction_row_key(fields: list[str], row: Sequence[Any]) -> tuple[Any, ...]:
    mapping = _row_map(fields, row)
    if mapping:
        return (
            mapping.get("business_time"),
            mapping.get("trade_index"),
            mapping.get("business_direction"),
            mapping.get("business_amount"),
            mapping.get("hq_px"),
            mapping.get("buy_no"),
            mapping.get("sell_no"),
            mapping.get("channel_num"),
        )
    return tuple(row)


def _dedupe_state(symbol: str, kind: str) -> dict[str, Any]:
    symbol_state = _MODULE_L2_DEDUPE_STATE.setdefault(normalize_symbol(symbol), {})
    state = symbol_state.get(kind)
    if state is None:
        state = {"queue": deque(), "seen": set()}
        symbol_state[kind] = state
    return state


def _dedupe_payload(symbol: str, kind: str, payload: Any) -> dict[str, Any] | None:
    fields, rows = _extract_symbol_rows(payload, symbol)
    if not rows:
        return None
    state = _dedupe_state(symbol, kind)
    queue: deque[tuple[Any, ...]] = state["queue"]
    seen: set[tuple[Any, ...]] = state["seen"]
    delta_rows: list[list[Any]] = []
    key_builder = _entrust_row_key if kind == "entrust" else _transaction_row_key
    max_keys = max(100, _config().postgres.dedupe_window)
    for row in reversed(rows):
        row_key = key_builder(fields, row)
        if row_key in seen:
            continue
        delta_rows.append(row)
        queue.append(row_key)
        seen.add(row_key)
    while len(queue) > max_keys:
        seen.discard(queue.popleft())
    if not delta_rows:
        return None
    return {"symbol": normalize_symbol(symbol), "fields": fields, "rows": delta_rows}


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
        if config.auto_create_tables:
            self.ensure_tables()

    def close(self) -> None:
        self.connection.close()

    def ensure_tables(self) -> None:
        sql = f"""
            create table if not exists public.{self.config.level2_table} (
                id bigserial primary key,
                account_id text not null,
                strategy_name text not null,
                source text not null default 'ptrade',
                trade_date date not null,
                symbol text not null,
                quote_time_text text,
                quote_source text not null default 'snapshot',
                last_price numeric(18, 6),
                open_price numeric(18, 6),
                high_price numeric(18, 6),
                low_price numeric(18, 6),
                pre_close numeric(18, 6),
                volume numeric(20, 2),
                turnover numeric(20, 2),
                bid1_price numeric(18, 6),
                bid1_volume numeric(20, 2),
                ask1_price numeric(18, 6),
                ask1_volume numeric(20, 2),
                has_l2 boolean,
                bid_level_count integer,
                ask_level_count integer,
                entrust_total_count integer,
                transaction_total_count integer,
                entrust_delta_count integer,
                transaction_delta_count integer,
                snapshot_payload_json jsonb,
                entrust_payload_json jsonb,
                transaction_payload_json jsonb,
                entrust_delta_json jsonb,
                transaction_delta_json jsonb,
                raw_json jsonb not null,
                created_at timestamptz not null default now()
            );
            create index if not exists idx_{self.config.level2_table}_symbol_created_at
                on public.{self.config.level2_table} (symbol, created_at desc);
            create index if not exists idx_{self.config.level2_table}_trade_date_symbol
                on public.{self.config.level2_table} (trade_date, symbol);
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)

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

    def insert_level2_raw(self, strategy_name: str, quote: QuoteSnapshot, capture: dict[str, Any]) -> None:
        if not self.config.write_level2:
            return
        snapshot_payload = _json_ready(capture.get("snapshot_payload", quote.raw))
        entrust_payload = _json_ready(capture.get("entrust_payload"))
        transaction_payload = _json_ready(capture.get("transaction_payload"))
        entrust_delta = _json_ready(capture.get("entrust_delta"))
        transaction_delta = _json_ready(capture.get("transaction_delta"))
        bid1_price, bid1_volume = _top_of_book(quote.bid)
        ask1_price, ask1_volume = _top_of_book(quote.ask)
        sql = f"""
            insert into public.{self.config.level2_table} (
                account_id, strategy_name, source, trade_date, symbol, quote_time_text, quote_source,
                last_price, open_price, high_price, low_price, pre_close, volume, turnover,
                bid1_price, bid1_volume, ask1_price, ask1_volume,
                has_l2, bid_level_count, ask_level_count,
                entrust_total_count, transaction_total_count, entrust_delta_count, transaction_delta_count,
                snapshot_payload_json, entrust_payload_json, transaction_payload_json,
                entrust_delta_json, transaction_delta_json, raw_json, created_at
            ) values (
                %s, %s, %s, current_date, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, now()
            )
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    self.config.account_id,
                    strategy_name,
                    self.config.source,
                    quote.symbol,
                    quote.timestamp,
                    str(capture.get("quote_source", "snapshot")),
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
                    bool(quote.bid or quote.ask),
                    len(quote.bid),
                    len(quote.ask),
                    int(capture.get("entrust_total_count", 0)),
                    int(capture.get("transaction_total_count", 0)),
                    int(capture.get("entrust_delta_count", 0)),
                    int(capture.get("transaction_delta_count", 0)),
                    Json(snapshot_payload),
                    Json(entrust_payload),
                    Json(transaction_payload),
                    Json(entrust_delta),
                    Json(transaction_delta),
                    Json(
                        {
                            "quote": asdict(quote),
                            "quote_source": capture.get("quote_source", "snapshot"),
                            "captured_at": datetime.now().isoformat(),
                            "entrust_total_count": capture.get("entrust_total_count", 0),
                            "transaction_total_count": capture.get("transaction_total_count", 0),
                            "entrust_delta_count": capture.get("entrust_delta_count", 0),
                            "transaction_delta_count": capture.get("transaction_delta_count", 0),
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


def _reset_intraday_state() -> None:
    global _MODULE_DAY_STAMP
    _MODULE_DAY_STAMP = time.strftime("%Y-%m-%d")
    _MODULE_LAST_CAPTURE_AT.clear()
    _MODULE_CAPTURE_COUNTS.clear()
    _MODULE_SAMPLED_SYMBOLS.clear()
    _MODULE_L2_DEDUPE_STATE.clear()


def _maybe_roll_day_state() -> None:
    if time.strftime("%Y-%m-%d") != _MODULE_DAY_STAMP:
        _reset_intraday_state()


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
        return api_func([symbol], data_count=data_count, start_pos=0, search_direction=1, is_dict=True)
    except TypeError:
        try:
            api_func = globals().get(api_name)
            if api_func is None:
                return None
            return api_func([symbol], data_count=data_count, start_pos=0, search_direction=1)
        except Exception as exc:
            _logger()(f"{api_name} failed for {symbol}: {exc}")
            return None
    except Exception as exc:
        _logger()(f"{api_name} failed for {symbol}: {exc}")
        return None


def _payload_row_count(payload: Any, symbol: str) -> int:
    _fields, rows = _extract_symbol_rows(payload, symbol)
    return len(rows)


def _payload_from_data(data: Any, symbol: str):
    if not isinstance(data, Mapping):
        return None
    for candidate in _symbol_key_candidates(symbol):
        if candidate in data:
            return data.get(candidate)
    return None


def _log_first_sample_once(symbol: str, capture: dict[str, Any], quote: QuoteSnapshot) -> None:
    if symbol in _MODULE_SAMPLED_SYMBOLS:
        return
    _MODULE_SAMPLED_SYMBOLS.add(symbol)
    sample = {
        "symbol": symbol,
        "quote_source": capture.get("quote_source"),
        "quote": asdict(quote),
        "entrust_total_count": capture.get("entrust_total_count", 0),
        "transaction_total_count": capture.get("transaction_total_count", 0),
        "entrust_delta_count": capture.get("entrust_delta_count", 0),
        "transaction_delta_count": capture.get("transaction_delta_count", 0),
    }
    _logger()(f"level2_first_sample[{symbol}]={json.dumps(sample, ensure_ascii=False, default=str)[:1200]}")


def _log_capture_probe(symbol: str, quote: QuoteSnapshot, capture: dict[str, Any]) -> None:
    cfg = _config()
    if not cfg.debug_logging:
        return
    cycle_count = _MODULE_CAPTURE_COUNTS.get(symbol, 0)
    if cycle_count <= 0 or cycle_count % cfg.log_interval_cycles != 0:
        return
    _logger()(
        f"level2_probe[{symbol}] cycle={cycle_count} "
        f"source={capture.get('quote_source')} last={quote.last_price:.3f} "
        f"has_l2={bool(quote.bid or quote.ask)} bid_levels={len(quote.bid)} ask_levels={len(quote.ask)} "
        f"entrust_total={capture.get('entrust_total_count', 0)} entrust_delta={capture.get('entrust_delta_count', 0)} "
        f"transaction_total={capture.get('transaction_total_count', 0)} transaction_delta={capture.get('transaction_delta_count', 0)}"
    )


def _build_capture(symbol: str, raw_payload) -> tuple[QuoteSnapshot, dict[str, Any]] | None:
    quote = _snapshot_for_symbol(symbol)
    quote_source = "snapshot"
    if quote is None:
        quote = normalize_quote(symbol, raw_payload)
        quote_source = "tick_data_fallback"
    if quote is None:
        return None
    cfg = _config()
    entrust_payload = None
    transaction_payload = None
    entrust_delta = None
    transaction_delta = None
    if cfg.postgres.capture_entrust:
        entrust_payload = _fetch_orderflow_payload("get_individual_entrust", symbol, cfg.postgres.entrust_data_count)
        entrust_delta = _dedupe_payload(symbol, "entrust", entrust_payload)
    if cfg.postgres.capture_transaction:
        transaction_payload = _fetch_orderflow_payload(
            "get_individual_transaction",
            symbol,
            cfg.postgres.transaction_data_count,
        )
        transaction_delta = _dedupe_payload(symbol, "transaction", transaction_payload)
    capture = {
        "quote_source": quote_source,
        "snapshot_payload": quote.raw,
        "tick_payload": raw_payload,
        "entrust_payload": entrust_payload,
        "transaction_payload": transaction_payload,
        "entrust_delta": entrust_delta,
        "transaction_delta": transaction_delta,
        "entrust_total_count": _payload_row_count(entrust_payload, symbol),
        "transaction_total_count": _payload_row_count(transaction_payload, symbol),
        "entrust_delta_count": len(entrust_delta.get("rows", [])) if isinstance(entrust_delta, Mapping) else 0,
        "transaction_delta_count": len(transaction_delta.get("rows", [])) if isinstance(transaction_delta, Mapping) else 0,
    }
    return quote, capture


def _should_capture(symbol: str, now_epoch: float) -> bool:
    last_capture = _MODULE_LAST_CAPTURE_AT.get(symbol, 0.0)
    if now_epoch - last_capture < _config().poll_interval_seconds:
        return False
    _MODULE_LAST_CAPTURE_AT[symbol] = now_epoch
    return True


def _process_symbol_cycle(symbol: str, raw_payload, trigger: str) -> None:
    _maybe_roll_day_state()
    normalized_symbol = normalize_symbol(symbol)
    now_epoch = time.time()
    if not _should_capture(normalized_symbol, now_epoch):
        return
    built = _build_capture(normalized_symbol, raw_payload)
    if built is None:
        return
    quote, capture = built
    _MODULE_CAPTURE_COUNTS[normalized_symbol] = _MODULE_CAPTURE_COUNTS.get(normalized_symbol, 0) + 1
    _log_first_sample_once(normalized_symbol, capture, quote)
    _log_capture_probe(normalized_symbol, quote, capture)
    if _pg_store() is not None:
        try:
            _pg_store().insert_level2_raw(_config().strategy_name, quote, capture)
        except Exception as exc:
            _logger()(f"postgres level2 sync skipped for {normalized_symbol}: {exc}")
    if _config().debug_logging and (
        capture.get("entrust_delta_count", 0) > 0 or capture.get("transaction_delta_count", 0) > 0
    ):
        _logger()(
            f"level2_capture[{normalized_symbol}] trigger={trigger} source={capture.get('quote_source')} "
            f"entrust_delta={capture.get('entrust_delta_count', 0)} transaction_delta={capture.get('transaction_delta_count', 0)}"
        )


def initialize(context):
    global _MODULE_CONFIG, _MODULE_PG_STORE
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
        except Exception as exc:
            _logger()(f"postgres bootstrap skipped: {exc}")
            _MODULE_PG_STORE = None
    _reset_intraday_state()
    try:
        g.universe = list(cfg.watchlist)
    except Exception:
        pass
    set_universe(list(cfg.watchlist))
    _safe_set_parameters(cfg.enable_l2)
    if cfg.backtest_mode:
        _logger()("warning: level2 active capture is intended for live/editor mode; backtest often cannot return get_snapshot/L2 data")
    _logger()(f"initialized strategy={cfg.strategy_name}, watchlist={cfg.watchlist}, pg_enabled={cfg.postgres.enabled}")


def before_trading_start(context, data):
    _reset_intraday_state()
    _logger()(f"before_trading_start watchlist={_config().watchlist}")


def handle_data(context, data):
    for symbol in _config().watchlist:
        raw_payload = _payload_from_data(data, symbol)
        _process_symbol_cycle(symbol, raw_payload, trigger="handle_data")


def tick_data(context, data):
    for symbol in _config().watchlist:
        raw_payload = _payload_from_data(data, symbol)
        _process_symbol_cycle(symbol, raw_payload, trigger="tick_data")


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
