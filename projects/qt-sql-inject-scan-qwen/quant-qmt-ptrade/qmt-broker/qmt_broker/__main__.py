import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from qmt_broker.bar_backfill import BarBackfillOptions, run_bar_backfill
from qmt_broker.bar_diagnostics import BarDiagnosticsOptions, run_bar_diagnostics
from qmt_broker.broker import MarketDataBroker
from qmt_broker.config import BrokerConfig, load_config_from_env
from qmt_broker.http_api import create_http_server
from qmt_broker.providers import (
    MockMarketDataProvider,
    MockTradeProvider,
    XtQuantMarketDataProvider,
    XtQuantTradeProvider,
)
from qmt_broker.security_master import PostgresSecurityMasterStore, SecurityMasterSyncOptions, sync_security_master
from qmt_broker.trade_broker import TradeBroker


def build_provider(provider_name: str):
    if provider_name == "mock":
        return MockMarketDataProvider()
    if provider_name == "xtquant":
        return XtQuantMarketDataProvider()
    try:
        return XtQuantMarketDataProvider()
    except Exception:
        return MockMarketDataProvider()


def build_trade_provider(provider_name: str, config: BrokerConfig):
    if provider_name == "mock":
        return MockTradeProvider()
    if provider_name == "xtquant":
        return XtQuantTradeProvider(config)
    try:
        return XtQuantTradeProvider(config)
    except Exception:
        return MockTradeProvider()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qmt-broker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="run the Windows-hosted sidecar")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    serve_parser.add_argument("--provider", choices=["auto", "xtquant", "mock"])
    serve_parser.add_argument("--trade-provider", choices=["auto", "xtquant", "mock"])
    serve_parser.add_argument("--token")

    backfill_bars_parser = subparsers.add_parser("backfill-bars", help="backfill intraday bars into PostgreSQL")
    backfill_bars_parser.add_argument("--provider", choices=["auto", "xtquant", "mock"])
    backfill_bars_parser.add_argument("--period", default="1m")
    backfill_bars_parser.add_argument("--trade-date", default="")
    backfill_bars_parser.add_argument("--start-time", default="")
    backfill_bars_parser.add_argument("--end-time", default="")
    backfill_bars_parser.add_argument("--symbols", default="")
    backfill_bars_parser.add_argument("--skip-prefetch", action="store_true")
    backfill_bars_parser.add_argument("--prefetch-batch-size", type=int, default=16)
    backfill_bars_parser.add_argument("--batch-fetch-rounds", type=int, default=2)
    backfill_bars_parser.add_argument("--fetch-retry-count", type=int, default=3)
    backfill_bars_parser.add_argument("--wait-timeout-ms", type=int, default=5000)
    backfill_bars_parser.add_argument("--poll-interval-ms", type=int, default=250)
    backfill_bars_parser.add_argument("--pg-dsn", default="")
    backfill_bars_parser.add_argument("--pg-schema", default="")
    backfill_bars_parser.add_argument("--pg-table", default="")

    diagnose_bars_parser = subparsers.add_parser("diagnose-bars-batch", help="diagnose intraday bars readability")
    diagnose_bars_parser.add_argument("--provider", choices=["auto", "xtquant", "mock"])
    diagnose_bars_parser.add_argument("--period", default="1m")
    diagnose_bars_parser.add_argument("--trade-date", default="")
    diagnose_bars_parser.add_argument("--start-time", default="")
    diagnose_bars_parser.add_argument("--end-time", default="")
    diagnose_bars_parser.add_argument("--symbols", default="")
    diagnose_bars_parser.add_argument("--skip-prefetch", action="store_true")
    diagnose_bars_parser.add_argument("--prefetch-batch-size", type=int, default=16)
    diagnose_bars_parser.add_argument("--limit", type=int, default=10)
    diagnose_bars_parser.add_argument("--wait-timeout-ms", type=int, default=5000)
    diagnose_bars_parser.add_argument("--poll-interval-ms", type=int, default=250)
    diagnose_bars_parser.add_argument("--output", default="")

    security_master_parser = subparsers.add_parser("sync-security-master", help="sync CN security master into PostgreSQL")
    security_master_parser.add_argument("--provider", choices=["auto", "xtquant", "mock"])
    security_master_parser.add_argument("--sectors", default="")
    security_master_parser.add_argument("--skip-detail", action="store_true")
    security_master_parser.add_argument("--dry-run", action="store_true")
    security_master_parser.add_argument("--pg-dsn", default="")
    security_master_parser.add_argument("--pg-schema", default="")
    security_master_parser.add_argument("--pg-table", default="")

    plan_backfill_parser = subparsers.add_parser(
        "run-bar-backfill-plan",
        help="manually run a serve-style bar backfill stage such as nightly_recent_days or weekend_gap_scan",
    )
    plan_backfill_parser.add_argument("--provider", choices=["auto", "xtquant", "mock"])
    plan_backfill_parser.add_argument(
        "--stage",
        required=True,
        choices=["lunch_repair", "close_finalize", "nightly_recent_days", "weekend_gap_scan"],
    )
    plan_backfill_parser.add_argument("--trade-date", default="")
    plan_backfill_parser.add_argument("--symbols", default="")
    plan_backfill_parser.add_argument("--dry-run", action="store_true")

    get_parser = subparsers.add_parser("get", help="query a remote qmt-broker instance")
    get_parser.add_argument(
        "kind",
        choices=["quote", "bars", "bars_diag", "ticks", "l2_quote", "l2_order", "l2_transaction", "prefetch"],
    )
    get_parser.add_argument("--url", required=True)
    get_parser.add_argument("--token", default="")
    get_parser.add_argument("--symbol", required=True)
    get_parser.add_argument("--period", default="1m")
    get_parser.add_argument("--limit", type=int, default=200)
    get_parser.add_argument("--start-time", default="")
    get_parser.add_argument("--end-time", default="")
    get_parser.add_argument("--prefetch", action="store_true")
    get_parser.add_argument("--wait-timeout-ms", type=int, default=0)
    get_parser.add_argument("--poll-interval-ms", type=int, default=250)

    stream_parser = subparsers.add_parser("stream", help="stream SSE market data from qmt-broker")
    stream_parser.add_argument("--url", required=True)
    stream_parser.add_argument("--token", default="")
    stream_parser.add_argument("--topics", required=True)
    stream_parser.add_argument("--symbol", default="")
    stream_parser.add_argument("--period", default="1m")
    stream_parser.add_argument("--market", default="")
    stream_parser.add_argument("--replay", type=int, default=0)

    trade_get_parser = subparsers.add_parser("trade-get", help="query remote trade state")
    trade_get_parser.add_argument(
        "kind",
        choices=[
            "status",
            "account_infos",
            "account_statuses",
            "policy",
            "notifications",
            "audit",
            "requests",
            "request",
            "request_by_seq",
            "request_by_order_id",
            "request_by_order_sysid",
            "request_by_trade_id",
            "asset",
            "orders",
            "order",
            "trades",
            "positions",
            "position",
            "credit_detail",
            "credit_compacts",
            "credit_subjects",
            "credit_slo_codes",
            "credit_assure",
        ],
    )
    trade_get_parser.add_argument("--url", required=True)
    trade_get_parser.add_argument("--token", default="")
    trade_get_parser.add_argument("--account-id", default="")
    trade_get_parser.add_argument("--account-type", default="")
    trade_get_parser.add_argument("--symbol", default="")
    trade_get_parser.add_argument("--order-id", type=int, default=0)
    trade_get_parser.add_argument("--order-sysid", default="")
    trade_get_parser.add_argument("--trade-id", default="")
    trade_get_parser.add_argument("--seq", default="")
    trade_get_parser.add_argument("--limit", type=int, default=50)
    trade_get_parser.add_argument("--request-id", default="")
    trade_get_parser.add_argument("--status", default="")

    trade_order_parser = subparsers.add_parser("trade-order", help="place remote trade order")
    trade_order_parser.add_argument("--url", required=True)
    trade_order_parser.add_argument("--token", default="")
    trade_order_parser.add_argument("--account-id", default="")
    trade_order_parser.add_argument("--account-type", default="")
    trade_order_parser.add_argument("--symbol", required=True)
    trade_order_parser.add_argument("--side", choices=["buy", "sell"], default="buy")
    trade_order_parser.add_argument("--volume", type=int, required=True)
    trade_order_parser.add_argument("--price", type=float, default=0.0)
    trade_order_parser.add_argument("--estimated-price", type=float, default=0.0)
    trade_order_parser.add_argument("--price-type", default="fix")
    trade_order_parser.add_argument("--order-type", type=int, default=0)
    trade_order_parser.add_argument("--strategy-name", default="")
    trade_order_parser.add_argument("--order-remark", default="")
    trade_order_parser.add_argument("--idempotency-key", default="")
    trade_order_parser.add_argument("--require-approval", action="store_true")
    trade_order_parser.add_argument("--async-order", action="store_true")

    trade_cancel_parser = subparsers.add_parser("trade-cancel", help="cancel remote trade order")
    trade_cancel_parser.add_argument("--url", required=True)
    trade_cancel_parser.add_argument("--token", default="")
    trade_cancel_parser.add_argument("--account-id", default="")
    trade_cancel_parser.add_argument("--account-type", default="")
    trade_cancel_parser.add_argument("--order-id", type=int, default=0)
    trade_cancel_parser.add_argument("--order-sysid", default="")
    trade_cancel_parser.add_argument("--market", default="")
    trade_cancel_parser.add_argument("--async-cancel", action="store_true")

    trade_approve_parser = subparsers.add_parser("trade-approve", help="approve a pending trade request")
    trade_approve_parser.add_argument("--url", required=True)
    trade_approve_parser.add_argument("--token", default="")
    trade_approve_parser.add_argument("--request-id", required=True)
    trade_approve_parser.add_argument("--approver-id", default="")
    trade_approve_parser.add_argument("--approver-secret", default="")

    trade_reject_parser = subparsers.add_parser("trade-reject", help="reject a pending trade request")
    trade_reject_parser.add_argument("--url", required=True)
    trade_reject_parser.add_argument("--token", default="")
    trade_reject_parser.add_argument("--request-id", required=True)
    trade_reject_parser.add_argument("--reason", default="")
    trade_reject_parser.add_argument("--approver-id", default="")
    trade_reject_parser.add_argument("--approver-secret", default="")

    trade_revoke_parser = subparsers.add_parser("trade-revoke", help="revoke a pending trade request")
    trade_revoke_parser.add_argument("--url", required=True)
    trade_revoke_parser.add_argument("--token", default="")
    trade_revoke_parser.add_argument("--request-id", required=True)
    trade_revoke_parser.add_argument("--reason", default="")

    trade_stream_parser = subparsers.add_parser("trade-stream", help="stream SSE trade events from qmt-broker")
    trade_stream_parser.add_argument("--url", required=True)
    trade_stream_parser.add_argument("--token", default="")
    trade_stream_parser.add_argument("--topics", required=True)
    trade_stream_parser.add_argument("--account-id", default="")
    trade_stream_parser.add_argument("--replay", type=int, default=0)

    return parser


def command_serve(args: argparse.Namespace) -> int:
    env_config = load_config_from_env()
    config = BrokerConfig(
        host=args.host or env_config.host,
        port=args.port or env_config.port,
        provider=args.provider or env_config.provider,
        trade_provider=args.trade_provider or env_config.trade_provider,
        token=args.token if args.token is not None else env_config.token,
        history_limit=env_config.history_limit,
        stream_queue_size=env_config.stream_queue_size,
        l2_poll_interval_ms=env_config.l2_poll_interval_ms,
        heartbeat_interval_sec=env_config.heartbeat_interval_sec,
        tick_keepalive_ttl_sec=env_config.tick_keepalive_ttl_sec,
        tick_keepalive_poll_sec=env_config.tick_keepalive_poll_sec,
        tick_keepalive_source_refresh_sec=env_config.tick_keepalive_source_refresh_sec,
        tick_keepalive_max_symbols=env_config.tick_keepalive_max_symbols,
        tick_redis_url=env_config.tick_redis_url,
        tick_redis_key_prefix=env_config.tick_redis_key_prefix,
        tick_redis_ttl_sec=env_config.tick_redis_ttl_sec,
        tick_redis_max_records=env_config.tick_redis_max_records,
        tick_redis_reconnect_retry_sec=env_config.tick_redis_reconnect_retry_sec,
        tick_archive_pg_dsn=env_config.tick_archive_pg_dsn,
        tick_archive_pg_schema=env_config.tick_archive_pg_schema,
        tick_archive_table=env_config.tick_archive_table,
        tick_archive_batch_size=env_config.tick_archive_batch_size,
        tick_archive_flush_interval_sec=env_config.tick_archive_flush_interval_sec,
        tick_archive_queue_size=env_config.tick_archive_queue_size,
        tick_archive_reconnect_retry_sec=env_config.tick_archive_reconnect_retry_sec,
        tick_archive_backfill_enabled=env_config.tick_archive_backfill_enabled,
        tick_archive_backfill_poll_sec=env_config.tick_archive_backfill_poll_sec,
        tick_archive_backfill_retry_sec=env_config.tick_archive_backfill_retry_sec,
        bar_archive_pg_dsn=env_config.bar_archive_pg_dsn,
        bar_archive_pg_schema=env_config.bar_archive_pg_schema,
        bar_archive_table=env_config.bar_archive_table,
        bar_backfill_enabled=env_config.bar_backfill_enabled,
        bar_backfill_poll_sec=env_config.bar_backfill_poll_sec,
        bar_backfill_retry_sec=env_config.bar_backfill_retry_sec,
        bar_backfill_lunch_window_start=env_config.bar_backfill_lunch_window_start,
        bar_backfill_lunch_window_end=env_config.bar_backfill_lunch_window_end,
        bar_backfill_close_window_start=env_config.bar_backfill_close_window_start,
        bar_backfill_close_window_end=env_config.bar_backfill_close_window_end,
        bar_backfill_nightly_enabled=env_config.bar_backfill_nightly_enabled,
        bar_backfill_nightly_window_start=env_config.bar_backfill_nightly_window_start,
        bar_backfill_nightly_window_end=env_config.bar_backfill_nightly_window_end,
        bar_backfill_recent_days=env_config.bar_backfill_recent_days,
        bar_backfill_weekend_enabled=env_config.bar_backfill_weekend_enabled,
        bar_backfill_weekend_window_start=env_config.bar_backfill_weekend_window_start,
        bar_backfill_weekend_window_end=env_config.bar_backfill_weekend_window_end,
        bar_backfill_weekend_lookback_days=env_config.bar_backfill_weekend_lookback_days,
        bar_backfill_weekend_max_trade_days=env_config.bar_backfill_weekend_max_trade_days,
        bar_backfill_symbol_workers=env_config.bar_backfill_symbol_workers,
        bar_backfill_provider_max_concurrency=env_config.bar_backfill_provider_max_concurrency,
        bar_backfill_symbol_timeout_sec=env_config.bar_backfill_symbol_timeout_sec,
        bar_backfill_coverage_table=env_config.bar_backfill_coverage_table,
        bar_backfill_jobs_table=env_config.bar_backfill_jobs_table,
        security_master_pg_dsn=env_config.security_master_pg_dsn,
        security_master_pg_schema=env_config.security_master_pg_schema,
        security_master_table=env_config.security_master_table,
        security_master_default_sectors=env_config.security_master_default_sectors,
        trader_path=env_config.trader_path,
        trader_session_id=env_config.trader_session_id,
        trader_account_id=env_config.trader_account_id,
        trader_account_type=env_config.trader_account_type,
        trade_audit_log_path=env_config.trade_audit_log_path,
        allowed_accounts=env_config.allowed_accounts,
        allowed_account_types=env_config.allowed_account_types,
        allowed_symbols=env_config.allowed_symbols,
        blocked_symbols=env_config.blocked_symbols,
        allowed_sides=env_config.allowed_sides,
        max_order_volume=env_config.max_order_volume,
        max_order_value=env_config.max_order_value,
        allow_credit_queries=env_config.allow_credit_queries,
        allow_credit_orders=env_config.allow_credit_orders,
        trade_state_store_path=env_config.trade_state_store_path,
        require_order_approval=env_config.require_order_approval,
        approval_accounts=env_config.approval_accounts,
        approval_symbols=env_config.approval_symbols,
        approval_order_value=env_config.approval_order_value,
        approval_pending_ttl_sec=env_config.approval_pending_ttl_sec,
        approval_min_approvers=env_config.approval_min_approvers,
        approver_secrets=env_config.approver_secrets,
        approval_reminder_before_sec=env_config.approval_reminder_before_sec,
        approval_webhook_urls=env_config.approval_webhook_urls,
        wecom_webhook_url=env_config.wecom_webhook_url,
        telegram_bot_token=env_config.telegram_bot_token,
        telegram_chat_id=env_config.telegram_chat_id,
        feishu_webhook_url=env_config.feishu_webhook_url,
        watchlist_pg_dsn=env_config.watchlist_pg_dsn,
        watchlist_pg_schema=env_config.watchlist_pg_schema,
        watchlist_table=env_config.watchlist_table,
        positions_table=env_config.positions_table,
    )
    provider = build_provider(config.provider)
    trade_provider = build_trade_provider(config.trade_provider, config)
    market_broker = MarketDataBroker(provider, config)
    trade_broker = TradeBroker(trade_provider, config)
    server = None
    print(
        json.dumps(
            {
                "status": "binding",
                "host": config.host,
                "port": config.port,
                "provider": provider.name(),
                "trade_provider": trade_provider.name(),
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    try:
        server = create_http_server(market_broker, trade_broker, config)
        print(
            json.dumps(
                {
                    "status": "listening",
                    "host": config.host,
                    "port": config.port,
                    "provider": provider.name(),
                    "trade_provider": trade_provider.name(),
                },
                ensure_ascii=False,
            )
        )
        server.serve_forever()
    finally:
        if server is not None:
            server.server_close()
        market_broker.close()
        trade_broker.close()
    return 0


def command_backfill_bars(args: argparse.Namespace) -> int:
    env_config = load_config_from_env()
    provider_name = args.provider or env_config.provider
    provider = build_provider(provider_name)
    config = BrokerConfig(
        provider=provider_name,
        watchlist_pg_dsn=env_config.watchlist_pg_dsn,
        watchlist_pg_schema=env_config.watchlist_pg_schema,
        watchlist_table=env_config.watchlist_table,
        positions_table=env_config.positions_table,
        bar_archive_pg_dsn=env_config.bar_archive_pg_dsn,
        bar_archive_pg_schema=env_config.bar_archive_pg_schema,
        bar_archive_table=env_config.bar_archive_table,
    )
    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
    options = BarBackfillOptions(
        period=args.period,
        trade_date=args.trade_date,
        start_time=args.start_time,
        end_time=args.end_time,
        symbols=symbols,
        prefetch=not bool(args.skip_prefetch),
        prefetch_batch_size=args.prefetch_batch_size,
        batch_fetch_rounds=args.batch_fetch_rounds,
        wait_timeout_ms=args.wait_timeout_ms,
        poll_interval_ms=args.poll_interval_ms,
        fetch_retry_count=args.fetch_retry_count,
        archive_dsn=args.pg_dsn,
        archive_schema=args.pg_schema,
        archive_table=args.pg_table,
    )
    try:
        run_bar_backfill(provider, config, options)
    finally:
        provider.close()
    return 0


def command_sync_security_master(args: argparse.Namespace) -> int:
    env_config = load_config_from_env()
    provider_name = args.provider or env_config.provider
    provider = build_provider(provider_name)
    store = PostgresSecurityMasterStore(
        args.pg_dsn or env_config.security_master_pg_dsn,
        schema=args.pg_schema or env_config.security_master_pg_schema,
        table=args.pg_table or env_config.security_master_table,
    )
    sectors = tuple(item.strip() for item in args.sectors.split(",") if item.strip())
    if not sectors:
        sectors = tuple(env_config.security_master_default_sectors)
    options = SecurityMasterSyncOptions(
        sectors=sectors,
        include_detail=not bool(args.skip_detail),
        dry_run=bool(args.dry_run),
        dsn=args.pg_dsn or env_config.security_master_pg_dsn,
        schema=args.pg_schema or env_config.security_master_pg_schema,
        table=args.pg_table or env_config.security_master_table,
    )
    try:
        result = sync_security_master(provider, store, options)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        provider.close()
    return 0


def command_run_bar_backfill_plan(args: argparse.Namespace) -> int:
    env_config = load_config_from_env()
    provider_name = args.provider or env_config.provider
    provider = build_provider(provider_name)
    config = BrokerConfig(
        provider=provider_name,
        watchlist_pg_dsn=env_config.watchlist_pg_dsn,
        watchlist_pg_schema=env_config.watchlist_pg_schema,
        watchlist_table=env_config.watchlist_table,
        positions_table=env_config.positions_table,
        tick_keepalive_max_symbols=env_config.tick_keepalive_max_symbols,
        bar_archive_pg_dsn=env_config.bar_archive_pg_dsn,
        bar_archive_pg_schema=env_config.bar_archive_pg_schema,
        bar_archive_table=env_config.bar_archive_table,
        bar_backfill_enabled=False,
        bar_backfill_poll_sec=env_config.bar_backfill_poll_sec,
        bar_backfill_retry_sec=env_config.bar_backfill_retry_sec,
        bar_backfill_lunch_window_start=env_config.bar_backfill_lunch_window_start,
        bar_backfill_lunch_window_end=env_config.bar_backfill_lunch_window_end,
        bar_backfill_close_window_start=env_config.bar_backfill_close_window_start,
        bar_backfill_close_window_end=env_config.bar_backfill_close_window_end,
        bar_backfill_nightly_enabled=env_config.bar_backfill_nightly_enabled,
        bar_backfill_nightly_window_start=env_config.bar_backfill_nightly_window_start,
        bar_backfill_nightly_window_end=env_config.bar_backfill_nightly_window_end,
        bar_backfill_recent_days=env_config.bar_backfill_recent_days,
        bar_backfill_weekend_enabled=env_config.bar_backfill_weekend_enabled,
        bar_backfill_weekend_window_start=env_config.bar_backfill_weekend_window_start,
        bar_backfill_weekend_window_end=env_config.bar_backfill_weekend_window_end,
        bar_backfill_weekend_lookback_days=env_config.bar_backfill_weekend_lookback_days,
        bar_backfill_weekend_max_trade_days=env_config.bar_backfill_weekend_max_trade_days,
        bar_backfill_symbol_workers=env_config.bar_backfill_symbol_workers,
        bar_backfill_provider_max_concurrency=env_config.bar_backfill_provider_max_concurrency,
        bar_backfill_symbol_timeout_sec=env_config.bar_backfill_symbol_timeout_sec,
        bar_backfill_coverage_table=env_config.bar_backfill_coverage_table,
        bar_backfill_jobs_table=env_config.bar_backfill_jobs_table,
    )
    broker = MarketDataBroker(provider, config)
    broker.config.bar_backfill_enabled = True
    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
    try:
        result = broker.run_bar_backfill_plan_once(
            args.stage,
            trade_date_text=args.trade_date,
            symbols=symbols,
            dry_run=bool(args.dry_run),
        )
        print(json.dumps(result, ensure_ascii=False))
    finally:
        broker.close()
    return 0


def command_diagnose_bars_batch(args: argparse.Namespace) -> int:
    env_config = load_config_from_env()
    provider_name = args.provider or env_config.provider
    provider = build_provider(provider_name)
    config = BrokerConfig(
        provider=provider_name,
        watchlist_pg_dsn=env_config.watchlist_pg_dsn,
        watchlist_pg_schema=env_config.watchlist_pg_schema,
        watchlist_table=env_config.watchlist_table,
        positions_table=env_config.positions_table,
    )
    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
    options = BarDiagnosticsOptions(
        period=args.period,
        trade_date=args.trade_date,
        start_time=args.start_time,
        end_time=args.end_time,
        symbols=symbols,
        prefetch=not bool(args.skip_prefetch),
        prefetch_batch_size=args.prefetch_batch_size,
        limit=args.limit,
        wait_timeout_ms=args.wait_timeout_ms,
        poll_interval_ms=args.poll_interval_ms,
        output_path=args.output,
    )
    try:
        result = run_bar_diagnostics(provider, config, options)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        provider.close()
    return 0


def _request(url: str, token: str = "") -> urllib.request.Request:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", "Bearer %s" % token)
    return request


def _post_json(url: str, token: str, payload: dict) -> int:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
    )
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer %s" % token)
    try:
        with urllib.request.urlopen(request) as response:
            print(response.read().decode("utf-8"))
        return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1


def command_get(args: argparse.Namespace) -> int:
    params = {"symbol": args.symbol}
    if args.kind == "bars":
        params["period"] = args.period
        params["limit"] = str(args.limit)
        if args.start_time:
            params["start_time"] = args.start_time
        if args.end_time:
            params["end_time"] = args.end_time
        path = "/v1/market/bars"
    elif args.kind == "bars_diag":
        params["period"] = args.period
        params["limit"] = str(args.limit)
        params["prefetch"] = "1" if args.prefetch else "0"
        params["wait_timeout_ms"] = str(args.wait_timeout_ms)
        params["poll_interval_ms"] = str(args.poll_interval_ms)
        if args.start_time:
            params["start_time"] = args.start_time
        if args.end_time:
            params["end_time"] = args.end_time
        path = "/v1/market/bars/diagnostics"
    elif args.kind == "quote":
        path = "/v1/market/quote"
    elif args.kind == "prefetch":
        return _post_json(
            args.url.rstrip("/") + "/v1/market/prefetch",
            args.token,
            {
                "symbol": args.symbol,
                "period": args.period,
                "start_time": args.start_time,
                "end_time": args.end_time,
                "wait_timeout_ms": args.wait_timeout_ms,
                "poll_interval_ms": args.poll_interval_ms,
            },
        )
    elif args.kind == "ticks":
        params["limit"] = str(args.limit)
        if args.start_time:
            params["start_time"] = args.start_time
        if args.end_time:
            params["end_time"] = args.end_time
        path = "/v1/market/ticks"
    elif args.kind == "l2_quote":
        params["limit"] = str(args.limit)
        if args.start_time:
            params["start_time"] = args.start_time
        if args.end_time:
            params["end_time"] = args.end_time
        path = "/v1/market/l2/quote"
    elif args.kind == "l2_order":
        params["limit"] = str(args.limit)
        if args.start_time:
            params["start_time"] = args.start_time
        if args.end_time:
            params["end_time"] = args.end_time
        path = "/v1/market/l2/orders"
    else:
        params["limit"] = str(args.limit)
        if args.start_time:
            params["start_time"] = args.start_time
        if args.end_time:
            params["end_time"] = args.end_time
        path = "/v1/market/l2/transactions"
    url = args.url.rstrip("/") + path + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(_request(url, args.token)) as response:
            print(response.read().decode("utf-8"))
        return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1


def command_stream(args: argparse.Namespace) -> int:
    params = {
        "topics": args.topics,
        "symbol": args.symbol,
        "period": args.period,
        "market": args.market,
        "replay": str(args.replay),
    }
    url = args.url.rstrip("/") + "/v1/stream?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(_request(url, args.token), timeout=3600) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").rstrip()
                if line:
                    print(line)
        return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1


def command_trade_get(args: argparse.Namespace) -> int:
    params = {}
    if args.account_id:
        params["account_id"] = args.account_id
    if args.account_type:
        params["account_type"] = args.account_type
    if args.symbol:
        params["symbol"] = args.symbol
    if args.order_id:
        params["order_id"] = str(args.order_id)
    if args.order_sysid:
        params["order_sysid"] = args.order_sysid
    if args.trade_id:
        params["trade_id"] = args.trade_id
    if args.seq:
        params["seq"] = args.seq
    if args.request_id:
        params["request_id"] = args.request_id
    if args.status:
        params["status"] = args.status
    if args.limit:
        params["limit"] = str(args.limit)
    path_map = {
        "status": "/v1/trade/status",
        "account_infos": "/v1/trade/account-infos",
        "account_statuses": "/v1/trade/account-statuses",
        "policy": "/v1/trade/policy",
        "notifications": "/v1/trade/notifications",
        "audit": "/v1/trade/audit",
        "requests": "/v1/trade/requests",
        "request": "/v1/trade/request",
        "request_by_seq": "/v1/trade/request/by-seq",
        "request_by_order_id": "/v1/trade/request/by-order-id",
        "request_by_order_sysid": "/v1/trade/request/by-order-sysid",
        "request_by_trade_id": "/v1/trade/request/by-trade-id",
        "asset": "/v1/trade/asset",
        "orders": "/v1/trade/orders",
        "order": "/v1/trade/order",
        "trades": "/v1/trade/trades",
        "positions": "/v1/trade/positions",
        "position": "/v1/trade/position",
        "credit_detail": "/v1/trade/credit/detail",
        "credit_compacts": "/v1/trade/credit/compacts",
        "credit_subjects": "/v1/trade/credit/subjects",
        "credit_slo_codes": "/v1/trade/credit/slo-codes",
        "credit_assure": "/v1/trade/credit/assure",
    }
    path = path_map[args.kind]
    if params:
        path += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(_request(args.url.rstrip("/") + path, args.token)) as response:
            print(response.read().decode("utf-8"))
        return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1


def command_trade_order(args: argparse.Namespace) -> int:
    payload = {
        "account_id": args.account_id,
        "account_type": args.account_type,
        "symbol": args.symbol,
        "side": args.side,
        "volume": args.volume,
        "price": args.price,
        "estimated_price": args.estimated_price,
        "price_type": args.price_type,
        "strategy_name": args.strategy_name,
        "order_remark": args.order_remark,
        "idempotency_key": args.idempotency_key,
        "require_approval": args.require_approval,
        "async": args.async_order,
    }
    if args.order_type > 0:
        payload["order_type"] = args.order_type
    return _post_json(args.url.rstrip("/") + "/v1/trade/order", args.token, payload)


def command_trade_cancel(args: argparse.Namespace) -> int:
    payload = {
        "account_id": args.account_id,
        "account_type": args.account_type,
        "order_id": args.order_id,
        "order_sysid": args.order_sysid,
        "market": args.market,
        "async": args.async_cancel,
    }
    return _post_json(args.url.rstrip("/") + "/v1/trade/cancel", args.token, payload)


def command_trade_stream(args: argparse.Namespace) -> int:
    params = {
        "topics": args.topics,
        "account_id": args.account_id,
        "replay": str(args.replay),
    }
    url = args.url.rstrip("/") + "/v1/trade/stream?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(_request(url, args.token), timeout=3600) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").rstrip()
                if line:
                    print(line)
        return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1


def command_trade_approve(args: argparse.Namespace) -> int:
    return _post_json(
        args.url.rstrip("/") + "/v1/trade/approve",
        args.token,
        {
            "request_id": args.request_id,
            "approver_id": args.approver_id,
            "approver_secret": args.approver_secret,
        },
    )


def command_trade_reject(args: argparse.Namespace) -> int:
    return _post_json(
        args.url.rstrip("/") + "/v1/trade/reject",
        args.token,
        {
            "request_id": args.request_id,
            "reason": args.reason,
            "approver_id": args.approver_id,
            "approver_secret": args.approver_secret,
        },
    )


def command_trade_revoke(args: argparse.Namespace) -> int:
    return _post_json(
        args.url.rstrip("/") + "/v1/trade/revoke",
        args.token,
        {
            "request_id": args.request_id,
            "reason": args.reason,
        },
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "serve":
        return command_serve(args)
    if args.command == "backfill-bars":
        return command_backfill_bars(args)
    if args.command == "diagnose-bars-batch":
        return command_diagnose_bars_batch(args)
    if args.command == "sync-security-master":
        return command_sync_security_master(args)
    if args.command == "run-bar-backfill-plan":
        return command_run_bar_backfill_plan(args)
    if args.command == "get":
        return command_get(args)
    if args.command == "stream":
        return command_stream(args)
    if args.command == "trade-get":
        return command_trade_get(args)
    if args.command == "trade-order":
        return command_trade_order(args)
    if args.command == "trade-cancel":
        return command_trade_cancel(args)
    if args.command == "trade-stream":
        return command_trade_stream(args)
    if args.command == "trade-approve":
        return command_trade_approve(args)
    if args.command == "trade-reject":
        return command_trade_reject(args)
    if args.command == "trade-revoke":
        return command_trade_revoke(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
