from __future__ import annotations

import ast
import json
import time
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

try:
    import pymysql
except Exception:
    pymysql = None


INLINE_RUNTIME_CONFIG = {
    "strategy_name": "ptrade_tick_pg_capture_v1",
    "watchlist": ["600570.SS"],
    "enable_l2": False,
    "backtest_mode": True,
    "debug_logging": True,
    "log_interval_ticks": 20,
    "postgres": {
        "enabled": True,
        "driver": "mysql",
        "host": "127.0.0.1",
        "port": 3306,
        "database": "quant",
        "user": "root",
        "password": "123456",
        "connect_timeout_seconds": 3,
        "account_id": "ptrade",
        "source": "ptrade",
        "watchlist_table_priority": ["watchlist_ptrade", "watchlist"],
        "tick_table": "tick_ptrade_raw",
        "write_ticks": True,
        "auto_create_tables": True,
    },
}

NUMERIC_FIELDS = ("last_price", "price", "match", "new_price", "close", "last_px")

_MODULE_CONFIG = None
_MODULE_PG_STORE = None
_MODULE_TICK_COUNTS: dict[str, int] = {}
_MODULE_SAMPLED_SYMBOLS: set[str] = set()
_MODULE_NULL_PAYLOAD_SAMPLED_SYMBOLS: set[str] = set()


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
    driver: str = "postgres"
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = "quant"
    user: str = "postgres"
    password: str = ""
    connect_timeout_seconds: int = 3
    account_id: str = "ptrade"
    source: str = "ptrade"
    watchlist_table_priority: list[str] | None = None
    tick_table: str = "tick_ptrade_raw"
    write_ticks: bool = True
    auto_create_tables: bool = True

    def __post_init__(self) -> None:
        self.driver = str(self.driver or "postgres").strip().lower()
        if self.watchlist_table_priority is None:
            self.watchlist_table_priority = ["watchlist_ptrade", "watchlist"]


@dataclass(slots=True)
class RuntimeConfig:
    strategy_name: str
    watchlist: list[str]
    enable_l2: bool
    backtest_mode: bool
    debug_logging: bool
    log_interval_ticks: int
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
        strategy_name=payload.get("strategy_name", "ptrade_tick_pg_capture_v1"),
        watchlist=watchlist,
        enable_l2=bool(payload.get("enable_l2", False)),
        backtest_mode=bool(payload.get("backtest_mode", True)),
        debug_logging=bool(payload.get("debug_logging", True)),
        log_interval_ticks=max(1, int(payload.get("log_interval_ticks", 20))),
        postgres=PostgresConfig(**payload.get("postgres", {})),
    )


def _config() -> RuntimeConfig:
    if _MODULE_CONFIG is None:
        raise RuntimeError("runtime config is not initialized")
    return _MODULE_CONFIG


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


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
        level = _parse_level(_coerce_structure(item))
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


def _payload_from_data(data: Any, symbol: str):
    if not isinstance(data, Mapping):
        return None
    normalized_symbol = normalize_symbol(symbol)
    for candidate in (normalized_symbol, symbol, normalized_symbol.split(".", 1)[0]):
        if candidate in data:
            return data.get(candidate)
    return None


def _raw_attr(value: Any, *candidates: str) -> Any:
    for candidate in candidates:
        try:
            if hasattr(value, candidate):
                return getattr(value, candidate)
        except Exception:
            pass
    return None


def _bar_payload_from_data(data: Any, symbol: str) -> dict[str, Any] | None:
    candidate = _payload_from_data(data, symbol)
    if candidate is None and not isinstance(data, Mapping):
        try:
            candidate = data[symbol]
        except Exception:
            candidate = None
    if candidate is None:
        return None
    if isinstance(candidate, Mapping):
        return dict(candidate)
    payload = {
        "close": _raw_attr(candidate, "close", "price", "last_price"),
        "open": _raw_attr(candidate, "open", "open_price"),
        "high": _raw_attr(candidate, "high", "high_price"),
        "low": _raw_attr(candidate, "low", "low_price"),
        "volume": _raw_attr(candidate, "volume", "vol"),
        "turnover": _raw_attr(candidate, "money", "turnover", "amount"),
        "datetime": _raw_attr(candidate, "datetime", "dt", "date", "time"),
    }
    if all(value is None for value in payload.values()):
        return None
    return payload


def _log_null_payload_sample_once(symbol: str, data: Any) -> None:
    normalized_symbol = normalize_symbol(symbol)
    if normalized_symbol in _MODULE_NULL_PAYLOAD_SAMPLED_SYMBOLS:
        return
    _MODULE_NULL_PAYLOAD_SAMPLED_SYMBOLS.add(normalized_symbol)
    sample = {"symbol": normalized_symbol, "data_type": str(type(data))}
    if isinstance(data, Mapping):
        sample["mapping_keys"] = list(data.keys())[:20]
    else:
        sample["symbol_value"] = str(_coerce_structure(_raw_attr(data, normalized_symbol, symbol)))
    _logger()(f"tick_null_payload_sample[{normalized_symbol}]={json.dumps(sample, ensure_ascii=False, default=str)[:1200]}")


class PostgresRuntimeStore:
    def __init__(self, config: PostgresConfig):
        self.config = config
        if config.driver == "mysql":
            if pymysql is None:
                raise RuntimeError("PyMySQL is not available")
            self.connection = pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
                connect_timeout=config.connect_timeout_seconds,
                autocommit=True,
                charset="utf8mb4",
            )
        else:
            if psycopg2 is None or Json is None:
                raise RuntimeError("psycopg2 is not available")
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

    def _qualified_table(self, table_name: str) -> str:
        if self.config.driver == "mysql":
            return table_name
        return f"public.{table_name}"

    def _json_param(self, value: Any):
        prepared = _json_ready(value)
        if self.config.driver == "mysql":
            return json.dumps(prepared, ensure_ascii=False, default=str)
        return Json(prepared)

    def ensure_tables(self) -> None:
        if self.config.driver == "mysql":
            sql = f"""
                create table if not exists {self._qualified_table(self.config.tick_table)} (
                    id bigint not null auto_increment primary key,
                    account_id varchar(64) not null,
                    strategy_name varchar(128) not null,
                    source varchar(64) not null default 'ptrade',
                    trade_date date not null,
                    symbol varchar(32) not null,
                    quote_time_text varchar(64),
                    last_price decimal(18, 6) not null,
                    open_price decimal(18, 6),
                    high_price decimal(18, 6),
                    low_price decimal(18, 6),
                    pre_close decimal(18, 6),
                    volume decimal(20, 2),
                    turnover decimal(20, 2),
                    bid1_price decimal(18, 6),
                    bid1_volume decimal(20, 2),
                    ask1_price decimal(18, 6),
                    ask1_volume decimal(20, 2),
                    quote_source varchar(32) not null default 'tick_data',
                    has_l2 boolean,
                    bid_level_count integer,
                    ask_level_count integer,
                    spread_bps decimal(12, 4),
                    imbalance decimal(12, 6),
                    momentum decimal(12, 6),
                    entrust_count integer,
                    transaction_count integer,
                    action varchar(16) not null default 'HOLD',
                    score decimal(12, 6),
                    tick_payload_json json,
                    entrust_payload_json json,
                    transaction_payload_json json,
                    raw_json json not null,
                    created_at timestamp not null default current_timestamp,
                    index idx_{self.config.tick_table}_symbol_created_at (symbol, created_at),
                    index idx_{self.config.tick_table}_trade_date_symbol (trade_date, symbol)
                )
            """
        else:
            sql = f"""
                create table if not exists {self._qualified_table(self.config.tick_table)} (
                    id bigserial primary key,
                    account_id text not null,
                    strategy_name text not null,
                    source text not null default 'ptrade',
                    trade_date date not null,
                    symbol text not null,
                    quote_time_text text,
                    last_price numeric(18, 6) not null,
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
                    quote_source text not null default 'tick_data',
                    has_l2 boolean,
                    bid_level_count integer,
                    ask_level_count integer,
                    spread_bps numeric(12, 4),
                    imbalance numeric(12, 6),
                    momentum numeric(12, 6),
                    entrust_count integer,
                    transaction_count integer,
                    action text not null default 'HOLD',
                    score numeric(12, 6),
                    tick_payload_json jsonb,
                    entrust_payload_json jsonb,
                    transaction_payload_json jsonb,
                    raw_json jsonb not null,
                    created_at timestamptz not null default now()
                );
            """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            if self.config.driver != "mysql":
                cursor.execute(
                    f"""
                    create index if not exists idx_{self.config.tick_table}_symbol_created_at
                        on {self._qualified_table(self.config.tick_table)} (symbol, created_at desc)
                    """
                )
                cursor.execute(
                    f"""
                    create index if not exists idx_{self.config.tick_table}_trade_date_symbol
                        on {self._qualified_table(self.config.tick_table)} (trade_date, symbol)
                    """
                )

    def _table_exists(self, table_name: str) -> bool:
        with self.connection.cursor() as cursor:
            if self.config.driver == "mysql":
                cursor.execute(
                    """
                    select exists (
                        select 1
                        from information_schema.tables
                        where table_schema = database() and table_name = %s
                    )
                    """,
                    (table_name,),
                )
            else:
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
            cursor.execute(f"select ts_code from {self._qualified_table(table_name)} where ts_code is not null order by ts_code")
            rows = cursor.fetchall()
        watchlist = sorted({normalize_symbol(row[0]) for row in rows if row and row[0]})
        return table_name, watchlist

    def insert_tick_raw(self, strategy_name: str, quote: QuoteSnapshot, tick_payload: Any) -> None:
        if not self.config.write_ticks:
            return
        bid1_price, bid1_volume = _top_of_book(quote.bid)
        ask1_price, ask1_volume = _top_of_book(quote.ask)
        sql = f"""
            insert into {self._qualified_table(self.config.tick_table)} (
                account_id, strategy_name, source, trade_date, symbol, quote_time_text,
                last_price, open_price, high_price, low_price, pre_close, volume, turnover,
                bid1_price, bid1_volume, ask1_price, ask1_volume, quote_source, has_l2,
                bid_level_count, ask_level_count, spread_bps, imbalance, momentum,
                entrust_count, transaction_count, action, score, tick_payload_json,
                entrust_payload_json, transaction_payload_json, raw_json, created_at
            ) values (
                %s, %s, %s, current_date, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, current_timestamp
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
                    "tick_data",
                    bool(quote.bid or quote.ask),
                    len(quote.bid),
                    len(quote.ask),
                    None,
                    None,
                    None,
                    0,
                    0,
                    "HOLD",
                    None,
                    self._json_param(tick_payload if tick_payload is not None else quote.raw),
                    self._json_param(None),
                    self._json_param(None),
                    self._json_param({"quote": asdict(quote), "captured_at": datetime.now().isoformat()}),
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


def _log_first_sample_once(symbol: str, raw_payload: Any, quote: QuoteSnapshot) -> None:
    if symbol in _MODULE_SAMPLED_SYMBOLS:
        return
    _MODULE_SAMPLED_SYMBOLS.add(symbol)
    payload = {
        "symbol": symbol,
        "tick_payload": raw_payload,
        "normalized_quote": asdict(quote),
    }
    _logger()(f"tick_first_sample[{symbol}]={json.dumps(payload, ensure_ascii=False, default=str)[:1200]}")


def _log_tick_probe(symbol: str, quote: QuoteSnapshot) -> None:
    cfg = _config()
    if not cfg.debug_logging:
        return
    tick_count = _MODULE_TICK_COUNTS.get(symbol, 0)
    if tick_count <= 0 or tick_count % cfg.log_interval_ticks != 0:
        return
    _logger()(
        f"tick_probe[{symbol}] tick={tick_count} last={quote.last_price:.3f} "
        f"bid_levels={len(quote.bid)} ask_levels={len(quote.ask)} volume={quote.volume}"
    )


def _process_tick(symbol: str, raw_payload) -> None:
    quote = normalize_quote(symbol, raw_payload)
    if quote is None:
        if _config().debug_logging:
            _logger()(f"tick_parse_skipped[{normalize_symbol(symbol)}] payload={json.dumps(_json_ready(raw_payload), ensure_ascii=False)[:600]}")
        return
    normalized_symbol = normalize_symbol(symbol)
    _MODULE_TICK_COUNTS[normalized_symbol] = _MODULE_TICK_COUNTS.get(normalized_symbol, 0) + 1
    _log_first_sample_once(normalized_symbol, raw_payload, quote)
    _log_tick_probe(normalized_symbol, quote)
    if _MODULE_PG_STORE is not None:
        try:
            _MODULE_PG_STORE.insert_tick_raw(_config().strategy_name, quote, raw_payload)
        except Exception as exc:
            _logger()(f"postgres tick sync skipped for {normalized_symbol}: {exc}")


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
            _logger()(f"database bootstrap skipped[{cfg.postgres.driver}]: {exc}")
            _MODULE_PG_STORE = None
    _MODULE_TICK_COUNTS.clear()
    _MODULE_SAMPLED_SYMBOLS.clear()
    _MODULE_NULL_PAYLOAD_SAMPLED_SYMBOLS.clear()
    try:
        g.universe = list(cfg.watchlist)
    except Exception:
        pass
    set_universe(list(cfg.watchlist))
    _safe_set_parameters(cfg.enable_l2)
    if cfg.backtest_mode:
        _logger()("backtest_mode enabled: handle_data will also feed the same PG capture path because tick_data usually does not fire in backtests")
    _logger()(
        f"initialized strategy={cfg.strategy_name}, watchlist={cfg.watchlist}, "
        f"db_driver={cfg.postgres.driver}, db_enabled={cfg.postgres.enabled}"
    )


def before_trading_start(context, data):
    _MODULE_TICK_COUNTS.clear()
    _MODULE_SAMPLED_SYMBOLS.clear()
    _MODULE_NULL_PAYLOAD_SAMPLED_SYMBOLS.clear()
    _logger()(f"before_trading_start watchlist={_config().watchlist}")


def handle_data(context, data):
    if not _config().backtest_mode:
        return
    for symbol in _config().watchlist:
        raw_payload = _bar_payload_from_data(data, symbol)
        if raw_payload is None:
            _log_null_payload_sample_once(symbol, data)
        _process_tick(symbol, raw_payload)


def tick_data(context, data):
    for symbol in _config().watchlist:
        _process_tick(symbol, _payload_from_data(data, symbol))


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
