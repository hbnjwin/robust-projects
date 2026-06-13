from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


def normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
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


def load_runtime_config(path: str | Path) -> RuntimeConfig:
    config_path = Path(path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    signal_payload = payload.get("signal", {})
    signal = SignalConfig(**signal_payload)
    postgres_payload = payload.get("postgres", {})
    postgres = PostgresConfig(**postgres_payload)
    raw_watchlist = payload.get("watchlist", [])
    watchlist = sorted(
        {
            normalize_symbol(symbol)
            for symbol in raw_watchlist
            if isinstance(symbol, str) and symbol.strip()
        }
    )
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
