import json
import time
from dataclasses import dataclass
from datetime import datetime, time as daytime
from typing import Iterable, List, Optional, Sequence

from qmt_broker.bar_archive import PostgresBarArchive
from qmt_broker.config import BrokerConfig
from qmt_broker.providers.base import MarketDataProvider
from qmt_broker.symbol_sources import PostgresSymbolSource


def _emit_bar_backfill_log(event: str, **payload: object) -> None:
    message = {"ts_ms": int(time.time() * 1000), "event": event, "component": "bar_backfill", **payload}
    print(json.dumps(message, ensure_ascii=False), flush=True)


@dataclass
class BarBackfillOptions:
    period: str = "1m"
    trade_date: str = ""
    start_time: str = ""
    end_time: str = ""
    symbols: Sequence[str] = ()
    prefetch: bool = True
    prefetch_batch_size: int = 16
    batch_fetch_rounds: int = 2
    wait_timeout_ms: int = 5000
    poll_interval_ms: int = 250
    fetch_retry_count: int = 3
    archive_dsn: str = ""
    archive_schema: str = "public"
    archive_table: str = "intraday_bars_1m"


def run_bar_backfill(provider: MarketDataProvider, config: BrokerConfig, options: BarBackfillOptions) -> int:
    archive = PostgresBarArchive(
        options.archive_dsn or config.bar_archive_pg_dsn,
        schema=options.archive_schema or config.bar_archive_pg_schema,
        table=options.archive_table or config.bar_archive_table,
    )
    if not archive.enabled():
        raise RuntimeError("bar archive PG DSN is required")
    symbols = list(_load_symbols(config, options.symbols))
    if not symbols:
        raise RuntimeError("no symbols available for bar backfill")
    start_time, end_time = _resolve_window(options.trade_date, options.start_time, options.end_time)
    market_session = _get_market_session_snapshot()
    prefetch = _resolve_prefetch_enabled(options, start_time, market_session)
    _emit_bar_backfill_log(
        "bar_backfill_started",
        provider=provider.name(),
        period=options.period,
        trade_date=_trade_date_from_window(start_time),
        symbol_count=len(symbols),
        start_time=start_time,
        end_time=end_time,
        prefetch_requested=options.prefetch,
        prefetch=prefetch,
        market_session_status=market_session.get("status", "closed"),
    )
    written_symbols = 0
    written_rows = 0
    empty_symbols = 0
    warm_rows = {}
    if options.prefetch and not prefetch and _should_attempt_live_session_single_symbol_prefetch(options, symbols):
        _emit_bar_backfill_log(
            "bar_backfill_prefetch_single_started",
            provider=provider.name(),
            symbol=symbols[0],
            period=options.period,
            trade_date=_trade_date_from_window(start_time),
            start_time=start_time,
            end_time=end_time,
            reason="same_day_live_session_single_symbol",
            market_session_status=market_session.get("status", "closed"),
        )
        try:
            prefetch_result = provider.prefetch_history(
                symbols[0],
                options.period,
                start_time,
                end_time,
                wait_timeout_ms=options.wait_timeout_ms,
                poll_interval_ms=options.poll_interval_ms,
            )
        except Exception as exc:
            _emit_bar_backfill_log(
                "bar_backfill_prefetch_single_failed",
                provider=provider.name(),
                symbol=symbols[0],
                period=options.period,
                detail=str(exc),
            )
        else:
            _emit_bar_backfill_log(
                "bar_backfill_prefetch_single",
                provider=provider.name(),
                symbol=symbols[0],
                period=options.period,
                ok=bool(prefetch_result.get("ok")),
                cache_ready=bool(prefetch_result.get("cache_ready", False)),
                error=str(prefetch_result.get("error", "") or ""),
                detail=str(prefetch_result.get("detail", "") or ""),
            )
    elif options.prefetch and not prefetch:
        _emit_bar_backfill_log(
            "bar_backfill_prefetch_skipped",
            provider=provider.name(),
            period=options.period,
            trade_date=_trade_date_from_window(start_time),
            start_time=start_time,
            end_time=end_time,
            reason="same_day_live_session",
            market_session_status=market_session.get("status", "closed"),
        )
    if prefetch:
        _prefetch_bar_history_batches(
            provider,
            symbols,
            options.period,
            start_time,
            end_time,
            batch_size=max(int(options.prefetch_batch_size), 1),
            wait_timeout_ms=options.wait_timeout_ms,
            poll_interval_ms=options.poll_interval_ms,
        )
        warm_rows = _warm_bars_in_batches(
            provider,
            symbols,
            options.period,
            start_time,
            end_time,
            batch_size=max(int(options.prefetch_batch_size), 1),
            fetch_rounds=max(int(options.batch_fetch_rounds), 0),
            wait_timeout_ms=options.wait_timeout_ms,
            poll_interval_ms=options.poll_interval_ms,
        )
    for symbol_index, symbol in enumerate(symbols, start=1):
        _emit_bar_backfill_log(
            "bar_backfill_symbol_started",
            provider=provider.name(),
            symbol=symbol,
            symbol_index=symbol_index,
            total_symbols=len(symbols),
            period=options.period,
            start_time=start_time,
            end_time=end_time,
        )
        rows = warm_rows.get(symbol) or _fetch_bars_with_retry(
            provider,
            symbol,
            options.period,
            start_time,
            end_time,
            retry_count=max(int(options.fetch_retry_count), 0),
            poll_interval_ms=options.poll_interval_ms,
        )
        _emit_bar_backfill_log(
            "bar_backfill_provider_fetch",
            provider=provider.name(),
            symbol=symbol,
            period=options.period,
            record_count=len(rows),
            source="batch_warmup" if symbol in warm_rows else "direct",
        )
        if not rows:
            empty_symbols += 1
            _emit_bar_backfill_log(
                "bar_backfill_empty",
                provider=provider.name(),
                symbol=symbol,
                symbol_index=symbol_index,
                total_symbols=len(symbols),
                period=options.period,
                start_time=start_time,
                end_time=end_time,
            )
            continue
        written = archive.upsert_bars(symbol, options.period, rows, source=provider.name())
        written_symbols += 1
        written_rows += written
        _emit_bar_backfill_log(
            "bar_backfill_archived",
            provider=provider.name(),
            symbol=symbol,
            period=options.period,
            record_count=written,
        )
    _emit_bar_backfill_log(
        "bar_backfill_completed",
        provider=provider.name(),
        period=options.period,
        symbol_count=len(symbols),
        written_symbols=written_symbols,
        written_rows=written_rows,
        empty_symbols=empty_symbols,
    )
    return written_rows


def _load_symbols(config: BrokerConfig, explicit_symbols: Sequence[str]) -> Iterable[str]:
    normalized = [str(symbol or "").strip().upper() for symbol in explicit_symbols if str(symbol or "").strip()]
    if normalized:
        return tuple(dict.fromkeys(normalized))
    if not config.watchlist_pg_dsn:
        return ()
    source = PostgresSymbolSource(
        config.watchlist_pg_dsn,
        schema=config.watchlist_pg_schema,
        watchlist_table=config.watchlist_table,
        positions_table=config.positions_table,
    )
    return source.load().symbols


def _resolve_window(trade_date: str, start_time: str, end_time: str) -> tuple[str, str]:
    if start_time and end_time:
        return start_time, end_time
    if trade_date:
        compact = trade_date.replace("-", "")
    else:
        compact = datetime.now().strftime("%Y%m%d")
    start_value = start_time or f"{compact}093000"
    end_value = end_time or f"{compact}150000"
    return start_value, end_value


def _trade_date_from_window(start_time: str) -> str:
    text = str(start_time or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return ""


def _get_market_session_snapshot(now: Optional[datetime] = None) -> dict:
    current = now.astimezone() if now is not None else datetime.now().astimezone()
    clock = current.time()
    status = "closed"
    is_trading = False
    if current.weekday() >= 5:
        status = "weekend"
    elif daytime(9, 30) <= clock < daytime(11, 30) or daytime(13, 0) <= clock < daytime(15, 0):
        status = "trading"
        is_trading = True
    elif daytime(11, 30) <= clock < daytime(13, 0):
        status = "lunch_break"
    elif clock < daytime(9, 30):
        status = "pre_open"
    return {
        "market": "CN-A",
        "timezone": str(current.tzinfo or "local"),
        "now_local": current.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "is_trading": is_trading,
    }


def _resolve_prefetch_enabled(options: BarBackfillOptions, start_time: str, market_session: dict) -> bool:
    if not options.prefetch:
        return False
    period = str(options.period or "").strip().lower()
    if not period.endswith("m"):
        return True
    trade_date = _trade_date_from_window(start_time)
    if not trade_date:
        return True
    session_status = str(market_session.get("status") or "closed")
    if session_status not in {"trading", "lunch_break"}:
        return True
    current_date = str(market_session.get("now_local") or "").strip()[:10]
    if trade_date != current_date:
        return True
    return False


def _should_attempt_live_session_single_symbol_prefetch(options: BarBackfillOptions, symbols: Sequence[str]) -> bool:
    period = str(options.period or "").strip().lower()
    return len(symbols) == 1 and bool(options.prefetch) and period.endswith("m")


def _prefetch_bar_history_batches(
    provider: MarketDataProvider,
    symbols: Sequence[str],
    period: str,
    start_time: str,
    end_time: str,
    *,
    batch_size: int,
    wait_timeout_ms: int,
    poll_interval_ms: int,
) -> None:
    for batch_index, batch_symbols in enumerate(_chunked_symbols(symbols, batch_size), start=1):
        _emit_bar_backfill_log(
            "bar_backfill_prefetch_batch_started",
            provider=provider.name(),
            batch_index=batch_index,
            batch_size=len(batch_symbols),
            period=period,
            start_time=start_time,
            end_time=end_time,
            symbols=list(batch_symbols),
        )
        try:
            prefetch_result = provider.prefetch_history_batch(
                batch_symbols,
                period,
                start_time,
                end_time,
                wait_timeout_ms=wait_timeout_ms,
                poll_interval_ms=poll_interval_ms,
            )
        except Exception as exc:
            _emit_bar_backfill_log(
                "bar_backfill_prefetch_batch_failed",
                provider=provider.name(),
                batch_index=batch_index,
                batch_size=len(batch_symbols),
                period=period,
                detail=str(exc),
            )
            continue
        _emit_bar_backfill_log(
            "bar_backfill_prefetch_batch",
            provider=provider.name(),
            batch_index=batch_index,
            batch_size=len(batch_symbols),
            period=period,
            ok=bool(prefetch_result.get("ok")),
            ok_count=int(prefetch_result.get("ok_count", 0) or 0),
            cache_ready_count=int(prefetch_result.get("cache_ready_count", 0) or 0),
        )


def _warm_bars_in_batches(
    provider: MarketDataProvider,
    symbols: Sequence[str],
    period: str,
    start_time: str,
    end_time: str,
    *,
    batch_size: int,
    fetch_rounds: int,
    wait_timeout_ms: int,
    poll_interval_ms: int,
) -> dict:
    if fetch_rounds <= 0:
        return {}
    warm_rows = {}
    pending = list(symbols)
    sleep_sec = max(int(poll_interval_ms), 250) / 1000.0
    for round_index in range(1, fetch_rounds + 1):
        ready_count = 0
        ready_rows = 0
        ready_symbols = []
        next_pending = []
        for symbol in pending:
            rows = provider.get_bars(symbol, period, -1, start_time, end_time)
            if rows:
                warm_rows[symbol] = rows
                ready_count += 1
                ready_rows += len(rows)
                ready_symbols.append(symbol)
                continue
            next_pending.append(symbol)
        _emit_bar_backfill_log(
            "bar_backfill_batch_fetch_round",
            provider=provider.name(),
            round_index=round_index,
            fetch_rounds=fetch_rounds,
            symbol_count=len(pending),
            ready_count=ready_count,
            ready_rows=ready_rows,
            remaining_count=len(next_pending),
            ready_sample=ready_symbols[:3],
        )
        if not next_pending:
            break
        pending = next_pending
        if round_index >= fetch_rounds:
            break
        _prefetch_bar_history_batches(
            provider,
            pending,
            period,
            start_time,
            end_time,
            batch_size=batch_size,
            wait_timeout_ms=wait_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )
        time.sleep(sleep_sec)
    return warm_rows


def _chunked_symbols(symbols: Sequence[str], batch_size: int) -> List[tuple]:
    clean_batch_size = max(int(batch_size), 1)
    return [tuple(symbols[index : index + clean_batch_size]) for index in range(0, len(symbols), clean_batch_size)]


def _fetch_bars_with_retry(
    provider: MarketDataProvider,
    symbol: str,
    period: str,
    start_time: str,
    end_time: str,
    *,
    retry_count: int,
    poll_interval_ms: int,
) -> List[dict]:
    rows = provider.get_bars(symbol, period, -1, start_time, end_time)
    if rows or retry_count <= 0:
        return rows
    sleep_sec = max(int(poll_interval_ms), 250) / 1000.0
    for attempt in range(1, retry_count + 1):
        time.sleep(sleep_sec)
        rows = provider.get_bars(symbol, period, -1, start_time, end_time)
        _emit_bar_backfill_log(
            "bar_backfill_provider_retry",
            provider=provider.name(),
            symbol=symbol,
            period=period,
            attempt=attempt,
            retry_count=retry_count,
            record_count=len(rows),
        )
        if rows:
            return rows
    return rows
