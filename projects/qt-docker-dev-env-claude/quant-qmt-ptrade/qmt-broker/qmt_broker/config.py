import os
from dataclasses import dataclass, field
from typing import Dict, Tuple


def _split_csv(raw: str) -> Tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _parse_kv_csv(raw: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in _split_csv(raw):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            result[key] = value
    return result


@dataclass
class BrokerConfig:
    host: str = "127.0.0.1"
    port: int = 8711
    provider: str = "auto"
    trade_provider: str = "auto"
    token: str = ""
    history_limit: int = 2000
    stream_queue_size: int = 512
    l2_poll_interval_ms: int = 800
    heartbeat_interval_sec: int = 15
    tick_keepalive_ttl_sec: int = 900
    tick_keepalive_poll_sec: int = 1
    tick_keepalive_source_refresh_sec: int = 30
    tick_keepalive_max_symbols: int = 256
    tick_redis_url: str = ""
    tick_redis_key_prefix: str = "qmt-broker"
    tick_redis_ttl_sec: int = 900
    tick_redis_max_records: int = 512
    tick_redis_reconnect_retry_sec: int = 5
    tick_archive_pg_dsn: str = ""
    tick_archive_pg_schema: str = "public"
    tick_archive_table: str = "intraday_ticks"
    tick_archive_batch_size: int = 200
    tick_archive_flush_interval_sec: int = 1
    tick_archive_queue_size: int = 50000
    tick_archive_reconnect_retry_sec: int = 5
    tick_archive_backfill_enabled: bool = True
    tick_archive_backfill_poll_sec: int = 60
    tick_archive_backfill_retry_sec: int = 300
    bar_archive_pg_dsn: str = ""
    bar_archive_pg_schema: str = "public"
    bar_archive_table: str = "intraday_bars_1m"
    bar_backfill_enabled: bool = True
    bar_backfill_poll_sec: int = 30
    bar_backfill_retry_sec: int = 300
    bar_backfill_lunch_window_start: str = "11:35"
    bar_backfill_lunch_window_end: str = "11:50"
    bar_backfill_close_window_start: str = "15:10"
    bar_backfill_close_window_end: str = "15:30"
    bar_backfill_nightly_enabled: bool = True
    bar_backfill_nightly_window_start: str = "19:00"
    bar_backfill_nightly_window_end: str = "23:30"
    bar_backfill_recent_days: int = 7
    bar_backfill_weekend_enabled: bool = True
    bar_backfill_weekend_window_start: str = "09:00"
    bar_backfill_weekend_window_end: str = "18:00"
    bar_backfill_weekend_lookback_days: int = 365
    bar_backfill_weekend_max_trade_days: int = 20
    bar_backfill_symbol_workers: int = 2
    bar_backfill_provider_max_concurrency: int = 2
    bar_backfill_symbol_timeout_sec: int = 120
    bar_backfill_coverage_table: str = "intraday_bar_coverage_1m"
    bar_backfill_jobs_table: str = "intraday_bar_backfill_jobs"
    security_master_pg_dsn: str = ""
    security_master_pg_schema: str = "public"
    security_master_table: str = "security_master_cn"
    security_master_default_sectors: Tuple[str, ...] = ()
    trader_path: str = ""
    trader_session_id: int = 10001
    trader_account_id: str = ""
    trader_account_type: str = "STOCK"
    trade_audit_log_path: str = ".qmt-broker/trade-audit.jsonl"
    allowed_accounts: Tuple[str, ...] = ()
    allowed_account_types: Tuple[str, ...] = ()
    allowed_symbols: Tuple[str, ...] = ()
    blocked_symbols: Tuple[str, ...] = ()
    allowed_sides: Tuple[str, ...] = ("buy", "sell")
    max_order_volume: int = 0
    max_order_value: float = 0.0
    allow_credit_queries: bool = True
    allow_credit_orders: bool = False
    trade_state_store_path: str = ".qmt-broker/trade-state.json"
    require_order_approval: bool = False
    approval_accounts: Tuple[str, ...] = ()
    approval_symbols: Tuple[str, ...] = ()
    approval_order_value: float = 0.0
    approval_pending_ttl_sec: int = 3600
    approval_min_approvers: int = 1
    approver_secrets: Dict[str, str] = field(default_factory=dict)
    approval_reminder_before_sec: int = 300
    approval_webhook_urls: Tuple[str, ...] = ()
    wecom_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    feishu_webhook_url: str = ""
    watchlist_pg_dsn: str = ""
    watchlist_pg_schema: str = "public"
    watchlist_table: str = "watchlist"
    positions_table: str = "paper_positions"


def load_config_from_env() -> BrokerConfig:
    return BrokerConfig(
        host=os.environ.get("QMT_BROKER_HOST", "127.0.0.1"),
        port=int(os.environ.get("QMT_BROKER_PORT", "8711")),
        provider=os.environ.get("QMT_BROKER_PROVIDER", "auto"),
        trade_provider=os.environ.get("QMT_BROKER_TRADE_PROVIDER", os.environ.get("QMT_BROKER_PROVIDER", "auto")),
        token=os.environ.get("QMT_BROKER_TOKEN", ""),
        history_limit=int(os.environ.get("QMT_BROKER_HISTORY_LIMIT", "2000")),
        stream_queue_size=int(os.environ.get("QMT_BROKER_STREAM_QUEUE_SIZE", "512")),
        l2_poll_interval_ms=int(os.environ.get("QMT_BROKER_L2_POLL_INTERVAL_MS", "800")),
        heartbeat_interval_sec=int(os.environ.get("QMT_BROKER_HEARTBEAT_SEC", "15")),
        tick_keepalive_ttl_sec=max(30, int(os.environ.get("QMT_BROKER_TICK_KEEPALIVE_TTL_SEC", "900"))),
        tick_keepalive_poll_sec=max(1, int(os.environ.get("QMT_BROKER_TICK_KEEPALIVE_POLL_SEC", "1"))),
        tick_keepalive_source_refresh_sec=max(
            5, int(os.environ.get("QMT_BROKER_TICK_KEEPALIVE_SOURCE_REFRESH_SEC", "30"))
        ),
        tick_keepalive_max_symbols=max(1, int(os.environ.get("QMT_BROKER_TICK_KEEPALIVE_MAX_SYMBOLS", "256"))),
        tick_redis_url=os.environ.get("QMT_BROKER_TICK_REDIS_URL", ""),
        tick_redis_key_prefix=os.environ.get("QMT_BROKER_TICK_REDIS_KEY_PREFIX", "qmt-broker"),
        tick_redis_ttl_sec=max(30, int(os.environ.get("QMT_BROKER_TICK_REDIS_TTL_SEC", "900"))),
        tick_redis_max_records=max(1, int(os.environ.get("QMT_BROKER_TICK_REDIS_MAX_RECORDS", "512"))),
        tick_redis_reconnect_retry_sec=max(
            1, int(os.environ.get("QMT_BROKER_TICK_REDIS_RECONNECT_RETRY_SEC", "5"))
        ),
        tick_archive_pg_dsn=os.environ.get("QMT_BROKER_TICK_ARCHIVE_PG_DSN", ""),
        tick_archive_pg_schema=os.environ.get("QMT_BROKER_TICK_ARCHIVE_PG_SCHEMA", "public"),
        tick_archive_table=os.environ.get("QMT_BROKER_TICK_ARCHIVE_TABLE", "intraday_ticks"),
        tick_archive_batch_size=max(1, int(os.environ.get("QMT_BROKER_TICK_ARCHIVE_BATCH_SIZE", "200"))),
        tick_archive_flush_interval_sec=max(
            1, int(os.environ.get("QMT_BROKER_TICK_ARCHIVE_FLUSH_INTERVAL_SEC", "1"))
        ),
        tick_archive_queue_size=max(1, int(os.environ.get("QMT_BROKER_TICK_ARCHIVE_QUEUE_SIZE", "50000"))),
        tick_archive_reconnect_retry_sec=max(
            1, int(os.environ.get("QMT_BROKER_TICK_ARCHIVE_RECONNECT_RETRY_SEC", "5"))
        ),
        tick_archive_backfill_enabled=(
            os.environ.get("QMT_BROKER_TICK_ARCHIVE_BACKFILL_ENABLED", "1") not in {"0", "false", "False"}
        ),
        tick_archive_backfill_poll_sec=max(
            10, int(os.environ.get("QMT_BROKER_TICK_ARCHIVE_BACKFILL_POLL_SEC", "60"))
        ),
        tick_archive_backfill_retry_sec=max(
            30, int(os.environ.get("QMT_BROKER_TICK_ARCHIVE_BACKFILL_RETRY_SEC", "300"))
        ),
        bar_archive_pg_dsn=os.environ.get("QMT_BROKER_BAR_ARCHIVE_PG_DSN", ""),
        bar_archive_pg_schema=os.environ.get("QMT_BROKER_BAR_ARCHIVE_PG_SCHEMA", "public"),
        bar_archive_table=os.environ.get("QMT_BROKER_BAR_ARCHIVE_TABLE", "intraday_bars_1m"),
        bar_backfill_enabled=os.environ.get("QMT_BROKER_BAR_BACKFILL_ENABLED", "1") not in {"0", "false", "False"},
        bar_backfill_poll_sec=max(10, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_POLL_SEC", "30"))),
        bar_backfill_retry_sec=max(30, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_RETRY_SEC", "300"))),
        bar_backfill_lunch_window_start=os.environ.get("QMT_BROKER_BAR_BACKFILL_LUNCH_START", "11:35"),
        bar_backfill_lunch_window_end=os.environ.get("QMT_BROKER_BAR_BACKFILL_LUNCH_END", "11:50"),
        bar_backfill_close_window_start=os.environ.get("QMT_BROKER_BAR_BACKFILL_CLOSE_START", "15:10"),
        bar_backfill_close_window_end=os.environ.get("QMT_BROKER_BAR_BACKFILL_CLOSE_END", "15:30"),
        bar_backfill_nightly_enabled=(
            os.environ.get("QMT_BROKER_BAR_BACKFILL_NIGHTLY_ENABLED", "1") not in {"0", "false", "False"}
        ),
        bar_backfill_nightly_window_start=os.environ.get("QMT_BROKER_BAR_BACKFILL_NIGHTLY_START", "19:00"),
        bar_backfill_nightly_window_end=os.environ.get("QMT_BROKER_BAR_BACKFILL_NIGHTLY_END", "23:30"),
        bar_backfill_recent_days=max(1, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_RECENT_DAYS", "7"))),
        bar_backfill_weekend_enabled=(
            os.environ.get("QMT_BROKER_BAR_BACKFILL_WEEKEND_ENABLED", "1") not in {"0", "false", "False"}
        ),
        bar_backfill_weekend_window_start=os.environ.get("QMT_BROKER_BAR_BACKFILL_WEEKEND_START", "09:00"),
        bar_backfill_weekend_window_end=os.environ.get("QMT_BROKER_BAR_BACKFILL_WEEKEND_END", "18:00"),
        bar_backfill_weekend_lookback_days=max(
            30, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_WEEKEND_LOOKBACK_DAYS", "365"))
        ),
        bar_backfill_weekend_max_trade_days=max(
            1, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_WEEKEND_MAX_TRADE_DAYS", "20"))
        ),
        bar_backfill_symbol_workers=max(1, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_SYMBOL_WORKERS", "2"))),
        bar_backfill_provider_max_concurrency=max(
            1, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_PROVIDER_MAX_CONCURRENCY", "2"))
        ),
        bar_backfill_symbol_timeout_sec=max(
            10, int(os.environ.get("QMT_BROKER_BAR_BACKFILL_SYMBOL_TIMEOUT_SEC", "120"))
        ),
        bar_backfill_coverage_table=os.environ.get(
            "QMT_BROKER_BAR_BACKFILL_COVERAGE_TABLE", "intraday_bar_coverage_1m"
        ),
        bar_backfill_jobs_table=os.environ.get("QMT_BROKER_BAR_BACKFILL_JOBS_TABLE", "intraday_bar_backfill_jobs"),
        security_master_pg_dsn=os.environ.get(
            "QMT_BROKER_SECURITY_MASTER_PG_DSN",
            os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
        ),
        security_master_pg_schema=os.environ.get("QMT_BROKER_SECURITY_MASTER_PG_SCHEMA", "public"),
        security_master_table=os.environ.get("QMT_BROKER_SECURITY_MASTER_TABLE", "security_master_cn"),
        security_master_default_sectors=_split_csv(os.environ.get("QMT_BROKER_SECURITY_MASTER_SECTORS", "")),
        trader_path=os.environ.get("QMT_TRADER_PATH", ""),
        trader_session_id=int(os.environ.get("QMT_TRADER_SESSION_ID", "10001")),
        trader_account_id=os.environ.get("QMT_TRADER_ACCOUNT_ID", ""),
        trader_account_type=os.environ.get("QMT_TRADER_ACCOUNT_TYPE", "STOCK"),
        trade_audit_log_path=os.environ.get("QMT_BROKER_TRADE_AUDIT_LOG_PATH", ".qmt-broker/trade-audit.jsonl"),
        allowed_accounts=_split_csv(os.environ.get("QMT_BROKER_ALLOWED_ACCOUNTS", "")),
        allowed_account_types=tuple(
            item.upper() for item in _split_csv(os.environ.get("QMT_BROKER_ALLOWED_ACCOUNT_TYPES", ""))
        ),
        allowed_symbols=tuple(item.upper() for item in _split_csv(os.environ.get("QMT_BROKER_ALLOWED_SYMBOLS", ""))),
        blocked_symbols=tuple(item.upper() for item in _split_csv(os.environ.get("QMT_BROKER_BLOCKED_SYMBOLS", ""))),
        allowed_sides=tuple(item.lower() for item in _split_csv(os.environ.get("QMT_BROKER_ALLOWED_SIDES", "buy,sell"))),
        max_order_volume=int(os.environ.get("QMT_BROKER_MAX_ORDER_VOLUME", "0")),
        max_order_value=float(os.environ.get("QMT_BROKER_MAX_ORDER_VALUE", "0")),
        allow_credit_queries=os.environ.get("QMT_BROKER_ALLOW_CREDIT_QUERIES", "1") not in {"0", "false", "False"},
        allow_credit_orders=os.environ.get("QMT_BROKER_ALLOW_CREDIT_ORDERS", "0") in {"1", "true", "True"},
        trade_state_store_path=os.environ.get("QMT_BROKER_TRADE_STATE_STORE_PATH", ".qmt-broker/trade-state.json"),
        require_order_approval=os.environ.get("QMT_BROKER_REQUIRE_ORDER_APPROVAL", "0") in {"1", "true", "True"},
        approval_accounts=_split_csv(os.environ.get("QMT_BROKER_APPROVAL_ACCOUNTS", "")),
        approval_symbols=tuple(item.upper() for item in _split_csv(os.environ.get("QMT_BROKER_APPROVAL_SYMBOLS", ""))),
        approval_order_value=float(os.environ.get("QMT_BROKER_APPROVAL_ORDER_VALUE", "0")),
        approval_pending_ttl_sec=int(os.environ.get("QMT_BROKER_APPROVAL_PENDING_TTL_SEC", "3600")),
        approval_min_approvers=max(1, int(os.environ.get("QMT_BROKER_APPROVAL_MIN_APPROVERS", "1"))),
        approver_secrets=_parse_kv_csv(os.environ.get("QMT_BROKER_APPROVER_SECRETS", "")),
        approval_reminder_before_sec=max(0, int(os.environ.get("QMT_BROKER_APPROVAL_REMINDER_BEFORE_SEC", "300"))),
        approval_webhook_urls=_split_csv(os.environ.get("QMT_BROKER_APPROVAL_WEBHOOK_URLS", "")),
        wecom_webhook_url=os.environ.get("QMT_BROKER_WECOM_WEBHOOK_URL", ""),
        telegram_bot_token=os.environ.get("QMT_BROKER_TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("QMT_BROKER_TELEGRAM_CHAT_ID", ""),
        feishu_webhook_url=os.environ.get("QMT_BROKER_FEISHU_WEBHOOK_URL", ""),
        watchlist_pg_dsn=os.environ.get("QMT_BROKER_WATCHLIST_PG_DSN", ""),
        watchlist_pg_schema=os.environ.get("QMT_BROKER_WATCHLIST_PG_SCHEMA", "public"),
        watchlist_table=os.environ.get("QMT_BROKER_WATCHLIST_TABLE", "watchlist"),
        positions_table=os.environ.get("QMT_BROKER_POSITIONS_TABLE", "paper_positions"),
    )
