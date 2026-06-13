import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, time as daytime, timedelta
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple

from qmt_broker.bar_archive import PostgresBarArchive
from qmt_broker.bar_backfill import BarBackfillOptions, run_bar_backfill
from qmt_broker.bar_backfill_state import PostgresBarBackfillState
from qmt_broker.config import BrokerConfig
from qmt_broker.models import MarketEvent, StreamRequest, SubscriptionKey, SubscriptionTopic, unique_records_key
from qmt_broker.providers.base import MarketDataProvider
from qmt_broker.symbol_sources import PostgresSymbolSource, SymbolSourceSnapshot
from qmt_broker.tick_archive import PostgresTickArchive
from qmt_broker.tick_cache import RedisTickCache


@dataclass
class ProviderSubscriptionState:
    topic: SubscriptionTopic
    handle: str = ""
    watcher_count: int = 0
    l2_cursor: Optional[str] = None
    l2_day: str = ""
    last_error: str = ""
    last_poll_ms: int = 0


@dataclass
class QueueRegistration:
    queue_obj: "queue.Queue[Dict[str, object]]"
    topics: List[SubscriptionTopic]


@dataclass
class TickKeepaliveState:
    symbol: str
    handle: str = ""
    manual_touch_ms: int = 0
    pinned: bool = False
    last_error: str = ""


@dataclass
class BarKeepaliveState:
    symbol: str
    handle: str = ""
    last_error: str = ""


@dataclass(frozen=True)
class BarBackfillTask:
    trade_date_text: str
    stage: str
    start_time: str
    end_time: str
    symbols: Tuple[str, ...]


@dataclass(frozen=True)
class BarBackfillSymbolTask:
    symbol: str
    trade_date_text: str
    stage: str
    start_time: str
    end_time: str
    expected_bars: int
    task_index: int
    task_count: int
    symbol_index: int
    total_symbols: int
    attempt_key: str
    status_key: str
    job_key: str
    attempt_count: int
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    raw_context: Dict[str, object]
    progress_text: str


@dataclass(frozen=True)
class BarBackfillSymbolResult:
    status: str
    expected_bars: int
    actual_bars: int
    written_rows: int
    note: str = ""
    detail: str = ""
    first_bar_time: Optional[datetime] = None
    last_bar_time: Optional[datetime] = None


FULL_DAY_BAR_COVERAGE_STAGES = ("close_finalize", "nightly_recent_days", "weekend_gap_scan")


class MarketDataBroker:
    def __init__(
        self,
        provider: MarketDataProvider,
        config: BrokerConfig,
        tick_cache: Optional[RedisTickCache] = None,
        tick_archive: Optional[PostgresTickArchive] = None,
        bar_archive: Optional[PostgresBarArchive] = None,
    ) -> None:
        self.provider = provider
        self.config = config
        self._lock = threading.RLock()
        self._histories = defaultdict(lambda: deque(maxlen=self.config.history_limit))
        self._queues = {}
        self._provider_states: Dict[SubscriptionKey, ProviderSubscriptionState] = {}
        self._tick_keepalives: Dict[str, TickKeepaliveState] = {}
        self._bar_keepalives: Dict[str, BarKeepaliveState] = {}
        self._tick_cache = tick_cache or self._build_tick_cache(config)
        self._tick_archive = tick_archive or self._build_tick_archive(config)
        self._bar_archive = bar_archive or self._build_bar_archive(config)
        self._bar_backfill_state = self._build_bar_backfill_state(config)
        self._tick_source_snapshot = SymbolSourceSnapshot(symbols=(), metadata={"source": "disabled"})
        self._tick_source_last_error = ""
        self._tick_archive_backfill_last_run_ms = 0
        self._tick_archive_backfill_last_success_ms = 0
        self._tick_archive_backfill_last_error = ""
        self._tick_archive_backfill_next_run_ms = 0
        self._tick_archive_backfill_status: Dict[str, Dict[str, object]] = {}
        self._tick_archive_backfill_retry_at_ms: Dict[str, int] = {}
        self._tick_archive_backfill_completed_keys: Set[str] = set()
        self._bar_backfill_last_run_ms = 0
        self._bar_backfill_last_success_ms = 0
        self._bar_backfill_last_error = ""
        self._bar_backfill_next_run_ms = 0
        self._bar_backfill_status: Dict[str, Dict[str, object]] = {}
        self._bar_backfill_retry_at_ms: Dict[str, int] = {}
        self._bar_backfill_completed_keys: Set[str] = set()
        self._bar_backfill_attempt_counts: Dict[str, int] = {}
        self._tick_keepalive_pause_reason = ""
        self._tick_source = (
            PostgresSymbolSource(
                self.config.watchlist_pg_dsn,
                schema=self.config.watchlist_pg_schema,
                watchlist_table=self.config.watchlist_table,
                positions_table=self.config.positions_table,
                security_master_dsn=self.config.security_master_pg_dsn,
                security_master_schema=self.config.security_master_pg_schema,
                security_master_table=self.config.security_master_table,
            )
            if self.config.watchlist_pg_dsn
            else None
        )
        self._running = True
        self._refresh_tick_source()
        self._tick_archive.ping()
        self._bootstrap_tick_keepalives()
        self._bootstrap_bar_keepalives()
        self._l2_thread = threading.Thread(target=self._l2_poll_loop, daemon=True)
        self._tick_keepalive_thread = threading.Thread(target=self._tick_keepalive_loop, daemon=True)
        self._tick_archive_backfill_thread: Optional[threading.Thread] = None
        self._bar_backfill_thread: Optional[threading.Thread] = None
        if self._tick_archive.enabled() and self.config.tick_archive_backfill_enabled:
            self._tick_archive_backfill_thread = threading.Thread(target=self._tick_archive_backfill_loop, daemon=True)
        if self._bar_archive.enabled() and self.config.bar_backfill_enabled:
            self._bar_backfill_thread = threading.Thread(target=self._bar_backfill_loop, daemon=True)
        self._l2_thread.start()
        if self._tick_archive_backfill_thread is not None:
            self._tick_archive_backfill_thread.start()
        if self._bar_backfill_thread is not None:
            self._bar_backfill_thread.start()
        self._tick_keepalive_thread.start()

    def close(self) -> None:
        self._running = False
        self._l2_thread.join(timeout=1.0)
        self._tick_keepalive_thread.join(timeout=1.0)
        if self._tick_archive_backfill_thread is not None:
            self._tick_archive_backfill_thread.join(timeout=1.0)
        if self._bar_backfill_thread is not None:
            self._bar_backfill_thread.join(timeout=1.0)
        with self._lock:
            states = list(self._provider_states.values())
            tick_keepalives = [state.handle for state in self._tick_keepalives.values() if state.handle]
            bar_keepalives = [state.handle for state in self._bar_keepalives.values() if state.handle]
            self._provider_states.clear()
            self._tick_keepalives.clear()
            self._bar_keepalives.clear()
            self._queues.clear()
        for state in states:
            if state.handle:
                try:
                    self.provider.unsubscribe(state.handle)
                except Exception:
                    continue
        for handle in tick_keepalives:
            try:
                self.provider.unsubscribe(handle)
            except Exception:
                continue
        for handle in bar_keepalives:
            try:
                self.provider.unsubscribe(handle)
            except Exception:
                continue
        self._tick_archive.close()
        self._tick_cache.close()
        self.provider.close()

    def _emit_runtime_log(self, event: str, **payload: object) -> None:
        message = {"ts_ms": int(time.time() * 1000), "event": event, "provider": self.provider.name(), **payload}
        print(json.dumps(message, ensure_ascii=False), flush=True)

    def _progress_percent(self, completed: int, total: int) -> float:
        if total <= 0:
            return 100.0
        return round(min(max((completed / total) * 100.0, 0.0), 100.0), 1)

    def _bar_backfill_progress_text(
        self,
        *,
        task_index: int,
        task_count: int,
        symbol_index: int,
        total_symbols: int,
        overall_symbol_index: int,
        overall_symbol_count: int,
    ) -> str:
        return (
            f"task {task_index}/{task_count}, "
            f"symbol {symbol_index}/{total_symbols}, "
            f"overall {overall_symbol_index}/{overall_symbol_count}"
        )

    def _trim_runtime_text(self, value: str, limit: int = 400) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _extract_json_lines(self, text: str) -> List[Dict[str, object]]:
        payloads: List[Dict[str, object]] = []
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _run_bar_backfill_subprocess(self, symbol_task: BarBackfillSymbolTask) -> int:
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        pythonpath_entries = [str(repo_root)]
        if existing_pythonpath:
            pythonpath_entries.append(existing_pythonpath)
        env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)
        command = [
            sys.executable,
            "-m",
            "qmt_broker",
            "backfill-bars",
            "--provider",
            self.provider.name(),
            "--period",
            "1m",
            "--start-time",
            symbol_task.start_time,
            "--end-time",
            symbol_task.end_time,
            "--symbols",
            symbol_task.symbol,
            "--wait-timeout-ms",
            "5000",
            "--poll-interval-ms",
            "250",
            "--pg-dsn",
            self.config.bar_archive_pg_dsn,
            "--pg-schema",
            self.config.bar_archive_pg_schema,
            "--pg-table",
            self.config.bar_archive_table,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=max(int(self.config.bar_backfill_symbol_timeout_sec), 10),
                check=False,
                cwd=str(repo_root),
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"bar backfill subprocess timeout after {max(int(self.config.bar_backfill_symbol_timeout_sec), 10)}s"
            ) from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            raise RuntimeError(self._trim_runtime_text(detail))
        payloads = self._extract_json_lines(completed.stdout)
        for payload in reversed(payloads):
            if payload.get("event") == "bar_backfill_completed":
                return int(payload.get("written_rows", 0) or 0)
        return 0

    def _run_bar_backfill_symbol_task(self, symbol_task: BarBackfillSymbolTask) -> BarBackfillSymbolResult:
        archive_state = self._bar_archive.describe_bars_window(
            symbol_task.symbol,
            "1m",
            window_start=symbol_task.window_start,
            window_end=symbol_task.window_end,
        )
        current_count = int(archive_state.get("count", 0) or 0)
        if current_count >= symbol_task.expected_bars:
            return BarBackfillSymbolResult(
                status="complete",
                expected_bars=symbol_task.expected_bars,
                actual_bars=current_count,
                written_rows=0,
                note="archive_already_complete",
                first_bar_time=archive_state.get("first_bar_time"),
                last_bar_time=archive_state.get("last_bar_time"),
            )
        if self.config.bar_backfill_symbol_timeout_sec > 0:
            written_rows = self._run_bar_backfill_subprocess(symbol_task)
        else:
            written_rows = run_bar_backfill(
                self.provider,
                self.config,
                BarBackfillOptions(
                    period="1m",
                    start_time=symbol_task.start_time,
                    end_time=symbol_task.end_time,
                    symbols=(symbol_task.symbol,),
                    archive_dsn=self.config.bar_archive_pg_dsn,
                    archive_schema=self.config.bar_archive_pg_schema,
                    archive_table=self.config.bar_archive_table,
                ),
            )
        archive_state = self._bar_archive.describe_bars_window(
            symbol_task.symbol,
            "1m",
            window_start=symbol_task.window_start,
            window_end=symbol_task.window_end,
        )
        actual_bars = int(archive_state.get("count", 0) or 0)
        status = "complete" if actual_bars >= symbol_task.expected_bars else "partial" if actual_bars > 0 else "empty"
        note = ""
        if status != "complete":
            note = f"expected {symbol_task.expected_bars} bars, got {actual_bars}"
        return BarBackfillSymbolResult(
            status=status,
            expected_bars=symbol_task.expected_bars,
            actual_bars=actual_bars,
            written_rows=written_rows,
            note=note,
            first_bar_time=archive_state.get("first_bar_time"),
            last_bar_time=archive_state.get("last_bar_time"),
        )

    def _get_market_session_snapshot(self) -> Dict[str, object]:
        now = datetime.now().astimezone()
        clock = now.time()
        status = "closed"
        is_trading = False
        if now.weekday() >= 5:
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
            "timezone": str(now.tzinfo or "local"),
            "now_local": now.strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "is_trading": is_trading,
        }

    def _tick_keepalive_snapshot(self, symbol: str) -> Dict[str, object]:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return {}
        with self._lock:
            state = self._tick_keepalives.get(clean_symbol)
            return {
                "symbol": clean_symbol,
                "active": bool(state.handle) if state else False,
                "pinned": bool(state.pinned) if state else False,
                "manual_touch_ms": int(state.manual_touch_ms) if state else 0,
                "has_stream": self._has_active_tick_stream_locked(clean_symbol),
                "last_error": state.last_error if state else "",
            }

    def _build_tick_diagnostics(
        self,
        symbol: str,
        start_time: str,
        end_time: str,
        run_prefetch: bool,
        wait_timeout_ms: int,
        poll_interval_ms: int,
        market_session: Dict[str, object],
    ) -> Dict[str, object]:
        cache_status = self.get_tick_cache_status()
        return {
            "used_time_window": bool(start_time or end_time),
            "run_prefetch": run_prefetch,
            "wait_timeout_ms": wait_timeout_ms,
            "poll_interval_ms": poll_interval_ms,
            "cache_connected": bool(cache_status.get("connected")),
            "cache_backend": cache_status.get("backend", ""),
            "keepalive": self._tick_keepalive_snapshot(symbol),
            "market_session_status": market_session.get("status", "closed"),
            "empty_reason": "",
            "hint": "",
        }

    def _finalize_tick_diagnostics(
        self,
        diagnostics: Dict[str, object],
        records: List[Dict[str, object]],
        *,
        source: str,
    ) -> Dict[str, object]:
        finalized = dict(diagnostics)
        finalized["source"] = source
        finalized["result_count"] = len(records)
        if records:
            return finalized
        keepalive = finalized.get("keepalive") if isinstance(finalized.get("keepalive"), dict) else {}
        used_time_window = bool(finalized.get("used_time_window"))
        session_status = str(finalized.get("market_session_status") or "closed")
        if used_time_window:
            finalized["empty_reason"] = "provider_window_empty"
            finalized["hint"] = "指定了开始/结束时间，本次直接按时间窗从 provider 读取；空结果通常说明该窗口内没有可读 tick。"
        elif session_status in {"closed", "weekend", "pre_open"}:
            finalized["empty_reason"] = "market_closed_no_recent_ticks"
            finalized["hint"] = "当前不在连续交易时段；如果盘中没有提前积累热缓存，休市后再临时拉 recent ticks 通常会为空。"
        elif session_status == "lunch_break":
            finalized["empty_reason"] = "market_break_no_recent_ticks"
            finalized["hint"] = "当前处于午间休市，没有新增 tick 事件进入；可等待下午开盘或查看盘中已积累的热缓存。"
        elif keepalive.get("active"):
            finalized["empty_reason"] = "subscribed_but_no_tick_yet"
            finalized["hint"] = "tick 保活订阅已经建立，但等待窗口内还没有收到新的 tick 业务事件。"
        else:
            finalized["empty_reason"] = "no_recent_tick_events"
            finalized["hint"] = "当前没有可用的 recent tick 记录；可开启预热、检查流式面板，或在盘中再次重试。"
        return finalized

    def capabilities(self) -> Dict[str, object]:
        base = dict(self.provider.capabilities())
        base["stream_topics"] = [
            "quote",
            "bar",
            "tick",
            "whole_quote",
            "l2_quote",
            "l2_order",
            "l2_transaction",
        ]
        base["tick_keepalive"] = self.get_tick_keepalive_status()
        base["tick_cache"] = self.get_tick_cache_status()
        base["tick_archive"] = self.get_tick_archive_status()
        base["bar_backfill"] = self.get_bar_backfill_status()
        return base

    def get_quote(self, symbol: str) -> Dict[str, object]:
        return self.provider.get_quote(symbol)

    def get_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        return self.provider.get_bars(symbol, period, limit, start_time, end_time)

    def get_ticks(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> List[Dict[str, object]]:
        return self.get_ticks_response(
            symbol,
            limit,
            start_time,
            end_time,
            run_prefetch=run_prefetch,
            wait_timeout_ms=wait_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )["result"]

    def get_ticks_response(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        market_session = self._get_market_session_snapshot()
        diagnostics = self._build_tick_diagnostics(
            symbol,
            start_time,
            end_time,
            run_prefetch,
            wait_timeout_ms,
            poll_interval_ms,
            market_session,
        )
        if symbol and not start_time and not end_time:
            records = self._tick_cache.get_recent_ticks(symbol, limit)
            if records:
                return {
                    "result": records,
                    "source": "redis",
                    "market_session": market_session,
                    "diagnostics": self._finalize_tick_diagnostics(diagnostics, records, source="redis"),
                }
            with self._lock:
                records = self._recent_topic_payloads_locked(SubscriptionTopic(kind="tick", symbol=symbol), limit)
            if records:
                return {
                    "result": records,
                    "source": "stream_history",
                    "market_session": market_session,
                    "diagnostics": self._finalize_tick_diagnostics(diagnostics, records, source="stream_history"),
                }
        if run_prefetch and symbol and not start_time and not end_time:
            self.touch_tick_keepalive(symbol)
            source, records = self._wait_for_tick_history(symbol, limit, wait_timeout_ms, poll_interval_ms)
            if records:
                return {
                    "result": records,
                    "source": source,
                    "market_session": market_session,
                    "diagnostics": self._finalize_tick_diagnostics(diagnostics, records, source=source),
                }
        records = self.provider.get_ticks(
            symbol,
            limit,
            start_time,
            end_time,
            run_prefetch=run_prefetch,
            wait_timeout_ms=wait_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )
        return {
            "result": records,
            "source": "provider",
            "market_session": market_session,
            "diagnostics": self._finalize_tick_diagnostics(diagnostics, records, source="provider"),
        }

    def touch_tick_keepalive(self, symbol: str) -> None:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol:
            return
        now = int(time.time() * 1000)
        with self._lock:
            state = self._tick_keepalives.get(clean_symbol)
            if state is None:
                state = TickKeepaliveState(symbol=clean_symbol)
                self._tick_keepalives[clean_symbol] = state
            state.manual_touch_ms = now
            self._sync_tick_keepalives_locked(now)

    def get_tick_keepalive_status(self) -> Dict[str, object]:
        with self._lock:
            items = []
            for symbol in sorted(self._tick_keepalives.keys()):
                state = self._tick_keepalives[symbol]
                items.append(
                    {
                        "symbol": symbol,
                        "active": bool(state.handle),
                        "pinned": state.pinned,
                        "manual_touch_ms": state.manual_touch_ms,
                        "has_stream": self._has_active_tick_stream_locked(symbol),
                        "last_error": state.last_error,
                    }
                )
            return {
                "ok": True,
                "symbols": items,
                "source": dict(self._tick_source_snapshot.metadata),
                "source_symbols": list(self._tick_source_snapshot.symbols),
                "source_last_error": self._tick_source_last_error,
                "cache": self.get_tick_cache_status(),
                "archive": self.get_tick_archive_status(),
                "market_session": self._get_market_session_snapshot(),
            }

    def get_symbol_catalog(self) -> Dict[str, object]:
        with self._lock:
            snapshot = self._tick_source_snapshot
            names = dict(snapshot.symbol_names)
            watchlist_items = [{"symbol": symbol, "name": names.get(symbol, "")} for symbol in snapshot.watchlist_symbols]
            positions_items = [{"symbol": symbol, "name": names.get(symbol, "")} for symbol in snapshot.position_symbols]
            all_items = [{"symbol": symbol, "name": names.get(symbol, "")} for symbol in snapshot.symbols]
            return {
                "ok": True,
                "source": dict(snapshot.metadata),
                "watchlist": list(snapshot.watchlist_symbols),
                "positions": list(snapshot.position_symbols),
                "all": list(snapshot.symbols),
                "watchlist_items": watchlist_items,
                "positions_items": positions_items,
                "all_items": all_items,
                "symbol_names": names,
                "source_last_error": self._tick_source_last_error,
            }

    def get_tick_cache_status(self) -> Dict[str, object]:
        return self._tick_cache.status()

    def get_tick_archive_status(self) -> Dict[str, object]:
        status = dict(self._tick_archive.status())
        with self._lock:
            status["backfill"] = {
                "enabled": bool(self._tick_archive.enabled() and self.config.tick_archive_backfill_enabled),
                "last_run_ms": self._tick_archive_backfill_last_run_ms,
                "last_success_ms": self._tick_archive_backfill_last_success_ms,
                "last_error": self._tick_archive_backfill_last_error,
                "next_run_ms": self._tick_archive_backfill_next_run_ms,
                "symbols": dict(self._tick_archive_backfill_status),
            }
        return status

    def get_bar_backfill_status(self) -> Dict[str, object]:
        with self._lock:
            return {
                "enabled": bool(self._bar_archive.enabled() and self.config.bar_backfill_enabled),
                "last_run_ms": self._bar_backfill_last_run_ms,
                "last_success_ms": self._bar_backfill_last_success_ms,
                "last_error": self._bar_backfill_last_error,
                "next_run_ms": self._bar_backfill_next_run_ms,
                "symbols": dict(self._bar_backfill_status),
            }

    def get_tick_archive_records(
        self,
        symbol: str,
        trade_date: str = "",
        limit: int = 500,
    ) -> List[Dict[str, object]]:
        return self._tick_archive.query_ticks(symbol, trade_date, limit)

    def get_tick_archive_bars(
        self,
        symbol: str,
        trade_date: str = "",
        period: str = "1m",
        limit: int = 240,
    ) -> List[Dict[str, object]]:
        return self._tick_archive.query_bars(symbol, trade_date, period, limit)

    def get_tick_archive_features(
        self,
        symbol: str,
        trade_date: str = "",
    ) -> Dict[str, object]:
        return self._tick_archive.query_feature_summary(symbol, trade_date)

    def get_l2_quote(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        return self.provider.get_l2_quote(symbol, limit, start_time, end_time)

    def get_l2_order(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        return self.provider.get_l2_order(symbol, limit, start_time, end_time)

    def get_l2_transaction(
        self,
        symbol: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
    ) -> List[Dict[str, object]]:
        return self.provider.get_l2_transaction(symbol, limit, start_time, end_time)

    def prefetch_history(
        self,
        symbol: str,
        period: str,
        start_time: str = "",
        end_time: str = "",
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        return self.provider.prefetch_history(
            symbol,
            period,
            start_time,
            end_time,
            wait_timeout_ms=wait_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    def diagnose_bars(
        self,
        symbol: str,
        period: str,
        limit: int,
        start_time: str = "",
        end_time: str = "",
        run_prefetch: bool = False,
        wait_timeout_ms: int = 0,
        poll_interval_ms: int = 250,
    ) -> Dict[str, object]:
        return self.provider.diagnose_bars(
            symbol,
            period,
            limit,
            start_time,
            end_time,
            run_prefetch=run_prefetch,
            wait_timeout_ms=wait_timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    def open_stream(self, request: StreamRequest) -> Tuple[str, "queue.Queue[Dict[str, object]]"]:
        stream_queue = queue.Queue(self.config.stream_queue_size)
        stream_id = "stream-%d" % int(time.time() * 1000)
        with self._lock:
            self._queues[stream_id] = QueueRegistration(queue_obj=stream_queue, topics=request.topics)
            self._attach_topics(request.topics)
            if request.replay > 0:
                for topic in request.topics:
                    history = list(self._histories[topic.key()])[-request.replay :]
                    for payload in history:
                        stream_queue.put_nowait({"type": "replay", "event": payload})
        return stream_id, stream_queue

    def close_stream(self, stream_id: str) -> None:
        with self._lock:
            registration = self._queues.pop(stream_id, None)
            if registration is None:
                return
            self._detach_topics(registration.topics)

    def _attach_topics(self, topics: List[SubscriptionTopic]) -> None:
        for topic in topics:
            key = topic.key()
            state = self._provider_states.get(key)
            if state is None:
                state = ProviderSubscriptionState(topic=topic)
                self._provider_states[key] = state
                try:
                    state.handle = self.provider.subscribe(topic, self._on_provider_event)
                except Exception as exc:
                    state.last_error = str(exc)
            state.watcher_count += 1
        self._sync_tick_keepalives_locked(int(time.time() * 1000))

    def _detach_topics(self, topics: List[SubscriptionTopic]) -> None:
        for topic in topics:
            key = topic.key()
            state = self._provider_states.get(key)
            if state is None:
                continue
            state.watcher_count -= 1
            if state.watcher_count > 0:
                continue
            if state.handle:
                self.provider.unsubscribe(state.handle)
            self._provider_states.pop(key, None)
        self._sync_tick_keepalives_locked(int(time.time() * 1000))

    def _on_provider_event(self, topic: SubscriptionTopic, symbol: str, payload: Dict[str, object]) -> None:
        event = MarketEvent(topic=topic, symbol=symbol, payload=payload)
        encoded = event.to_dict()
        if topic.kind == "tick" and symbol:
            self._tick_cache.append_event(symbol, encoded)
            if self._should_archive_tick_symbol(symbol):
                self._tick_archive.append_event(symbol, encoded)
        elif topic.kind == "bar" and symbol and (topic.period or "1m") == "1m":
            self._archive_bar_event(symbol, topic.period or "1m", payload)
        with self._lock:
            self._histories[topic.key()].append(encoded)
            targets = list(self._queues.values())
        for registration in targets:
            if not self._matches(registration.topics, topic):
                continue
            try:
                registration.queue_obj.put_nowait({"type": "event", "event": encoded})
            except queue.Full:
                try:
                    registration.queue_obj.get_nowait()
                except queue.Empty:
                    pass
                try:
                    registration.queue_obj.put_nowait({"type": "event", "event": encoded})
                except queue.Full:
                    continue

    def _matches(self, stream_topics: List[SubscriptionTopic], incoming_topic: SubscriptionTopic) -> bool:
        for topic in stream_topics:
            if topic.kind != incoming_topic.kind:
                continue
            if topic.kind == "whole_quote":
                return topic.market == incoming_topic.market
            if topic.symbol != incoming_topic.symbol:
                continue
            if topic.kind == "bar" and topic.period != incoming_topic.period:
                continue
            return True
        return False

    def _recent_topic_payloads_locked(self, topic: SubscriptionTopic, limit: int) -> List[Dict[str, object]]:
        history = list(self._histories[topic.key()])[-max(limit, 1) :]
        payloads: List[Dict[str, object]] = []
        for item in history:
            payload = item.get("payload")
            if isinstance(payload, dict):
                payloads.append(payload)
        return payloads

    def _wait_for_tick_history(
        self,
        symbol: str,
        limit: int,
        wait_timeout_ms: int,
        poll_interval_ms: int,
    ) -> Tuple[str, List[Dict[str, object]]]:
        topic = SubscriptionTopic(kind="tick", symbol=symbol)
        deadline = time.time() + max(wait_timeout_ms, 0) / 1000.0
        interval_sec = max(poll_interval_ms, 50) / 1000.0
        while True:
            records = self._tick_cache.get_recent_ticks(symbol, limit)
            if records:
                return "redis", records
            with self._lock:
                records = self._recent_topic_payloads_locked(topic, limit)
            if records:
                return "stream_history", records
            if time.time() >= deadline:
                return "stream_history", []
            time.sleep(interval_sec)

    def _build_tick_cache(self, config: BrokerConfig) -> RedisTickCache:
        return RedisTickCache(
            config.tick_redis_url,
            key_prefix=config.tick_redis_key_prefix,
            max_records=config.tick_redis_max_records,
            ttl_sec=config.tick_redis_ttl_sec,
            reconnect_retry_sec=config.tick_redis_reconnect_retry_sec,
        )

    def _build_tick_archive(self, config: BrokerConfig) -> PostgresTickArchive:
        return PostgresTickArchive(
            config.tick_archive_pg_dsn,
            schema=config.tick_archive_pg_schema,
            table=config.tick_archive_table,
            batch_size=config.tick_archive_batch_size,
            flush_interval_sec=config.tick_archive_flush_interval_sec,
            queue_size=config.tick_archive_queue_size,
            reconnect_retry_sec=config.tick_archive_reconnect_retry_sec,
        )

    def _build_bar_archive(self, config: BrokerConfig) -> PostgresBarArchive:
        return PostgresBarArchive(
            config.bar_archive_pg_dsn,
            schema=config.bar_archive_pg_schema,
            table=config.bar_archive_table,
        )

    def _build_bar_backfill_state(self, config: BrokerConfig) -> PostgresBarBackfillState:
        return PostgresBarBackfillState(
            config.bar_archive_pg_dsn,
            schema=config.bar_archive_pg_schema,
            coverage_table=config.bar_backfill_coverage_table,
            jobs_table=config.bar_backfill_jobs_table,
        )

    def _trade_date_text(self) -> str:
        return datetime.now().astimezone().strftime("%Y-%m-%d")

    def _trade_window(self, trade_date_text: str) -> Tuple[str, str]:
        compact = trade_date_text.replace("-", "")
        return f"{compact}093000", f"{compact}150000"

    def _stage_trade_window(self, trade_date_text: str, stage: str) -> Tuple[str, str]:
        compact = trade_date_text.replace("-", "")
        if stage == "lunch_repair":
            return f"{compact}093000", f"{compact}113000"
        return f"{compact}093000", f"{compact}150000"

    def _resolve_bar_backfill_stage(self, market_session: Dict[str, object], now_local: datetime) -> str:
        status = str(market_session.get("status") or "closed")
        if status == "lunch_break" and self._within_window(
            now_local.time(),
            self.config.bar_backfill_lunch_window_start,
            self.config.bar_backfill_lunch_window_end,
        ):
            return "lunch_repair"
        if status == "closed" and self._within_window(
            now_local.time(),
            self.config.bar_backfill_close_window_start,
            self.config.bar_backfill_close_window_end,
        ):
            return "close_finalize"
        if (
            status == "closed"
            and self.config.bar_backfill_nightly_enabled
            and self._within_window(
                now_local.time(),
                self.config.bar_backfill_nightly_window_start,
                self.config.bar_backfill_nightly_window_end,
            )
        ):
            return "nightly_recent_days"
        if (
            status == "weekend"
            and self.config.bar_backfill_weekend_enabled
            and self._within_window(
                now_local.time(),
                self.config.bar_backfill_weekend_window_start,
                self.config.bar_backfill_weekend_window_end,
            )
        ):
            return "weekend_gap_scan"
        return ""

    def _resolve_bar_backfill_tasks(
        self,
        stage: str,
        *,
        trade_date_text: str,
        symbols: Tuple[str, ...],
    ) -> List[BarBackfillTask]:
        if not symbols:
            return []
        if stage in {"lunch_repair", "close_finalize"}:
            start_time, end_time = self._stage_trade_window(trade_date_text, stage)
            return [
                BarBackfillTask(
                    trade_date_text=trade_date_text,
                    stage=stage,
                    start_time=start_time,
                    end_time=end_time,
                    symbols=symbols,
                )
            ]
        if stage == "nightly_recent_days":
            candidate_dates = self._recent_weekday_trade_dates(
                self._parse_trade_date(trade_date_text),
                max(self.config.bar_backfill_recent_days, 1),
            )
            return self._build_gap_scan_tasks(candidate_dates, symbols, stage)
        if stage == "weekend_gap_scan":
            candidate_dates = self._lookback_weekday_trade_dates(
                self._parse_trade_date(trade_date_text),
                max(self.config.bar_backfill_weekend_lookback_days, 30),
            )
            return self._build_gap_scan_tasks(
                candidate_dates,
                symbols,
                stage,
                max_trade_days=max(self.config.bar_backfill_weekend_max_trade_days, 1),
            )
        return []

    def _within_window(self, clock: daytime, start_text: str, end_text: str) -> bool:
        start = self._parse_hhmm(start_text)
        end = self._parse_hhmm(end_text)
        return start <= clock <= end

    def _parse_hhmm(self, text: str) -> daytime:
        clean_text = str(text or "").strip()
        parts = clean_text.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            return daytime(0, 0)
        return daytime(hour=hour, minute=minute)

    def _parse_trade_date(self, trade_date_text: str) -> date:
        return datetime.strptime(str(trade_date_text or "").strip(), "%Y-%m-%d").date()

    def _recent_weekday_trade_dates(self, anchor_date: date, count: int) -> List[str]:
        results: List[str] = []
        cursor = anchor_date
        while len(results) < max(count, 1):
            if cursor.weekday() < 5:
                results.append(cursor.strftime("%Y-%m-%d"))
            cursor -= timedelta(days=1)
        return results

    def _lookback_weekday_trade_dates(self, anchor_date: date, lookback_days: int) -> List[str]:
        results: List[str] = []
        for offset in range(max(lookback_days, 1)):
            current = anchor_date - timedelta(days=offset)
            if current.weekday() < 5:
                results.append(current.strftime("%Y-%m-%d"))
        return results

    def _build_gap_scan_tasks(
        self,
        candidate_dates: List[str],
        symbols: Tuple[str, ...],
        stage: str,
        *,
        max_trade_days: int = 0,
    ) -> List[BarBackfillTask]:
        if not candidate_dates or not symbols:
            return []
        if not self._bar_backfill_state.enabled():
            return []
        try:
            coverage_rows = self._bar_backfill_state.load_coverage_rows(
                symbols=symbols,
                trade_date_from=self._parse_trade_date(candidate_dates[-1]),
                trade_date_to=self._parse_trade_date(candidate_dates[0]),
                period="1m",
                stages=FULL_DAY_BAR_COVERAGE_STAGES,
            )
        except Exception as exc:
            self._emit_runtime_log("bar_backfill_gap_scan_coverage_failed", stage=stage, detail=str(exc))
            return []
        completed_pairs = {
            (row["trade_date"].strftime("%Y-%m-%d"), str(row.get("ts_code") or "").strip().upper())
            for row in coverage_rows
            if str(row.get("status") or "").strip().lower() == "complete"
            and int(row.get("expected_bars") or 0) > 0
            and int(row.get("actual_bars") or 0) >= int(row.get("expected_bars") or 0)
        }
        empty_pairs = {
            (row["trade_date"].strftime("%Y-%m-%d"), str(row.get("ts_code") or "").strip().upper())
            for row in coverage_rows
            if str(row.get("status") or "").strip().lower() == "empty"
        }
        tasks: List[BarBackfillTask] = []
        for trade_date_text in candidate_dates:
            missing_symbols = tuple(
                symbol
                for symbol in symbols
                if (trade_date_text, str(symbol or "").strip().upper()) not in completed_pairs
                and (
                    stage != "weekend_gap_scan"
                    or (trade_date_text, str(symbol or "").strip().upper()) not in empty_pairs
                )
            )
            if not missing_symbols:
                continue
            start_time, end_time = self._stage_trade_window(trade_date_text, stage)
            tasks.append(
                BarBackfillTask(
                    trade_date_text=trade_date_text,
                    stage=stage,
                    start_time=start_time,
                    end_time=end_time,
                    symbols=missing_symbols,
                )
            )
            if max_trade_days > 0 and len(tasks) >= max_trade_days:
                break
        return tasks

    def _tick_archive_backfill_loop(self) -> None:
        interval_sec = max(self.config.tick_archive_backfill_poll_sec, 10)
        while self._running:
            now_ms = int(time.time() * 1000)
            try:
                self._run_tick_archive_backfill_cycle(now_ms)
            except Exception as exc:
                with self._lock:
                    self._tick_archive_backfill_last_error = str(exc)
                    self._tick_archive_backfill_last_run_ms = now_ms
                    self._tick_archive_backfill_next_run_ms = now_ms + interval_sec * 1000
                self._emit_runtime_log("tick_archive_backfill_cycle_failed", detail=str(exc))
            time.sleep(interval_sec)

    def _run_tick_archive_backfill_cycle(self, now_ms: int) -> None:
        if not self._tick_archive.enabled() or not self.config.tick_archive_backfill_enabled:
            return
        market_session = self._get_market_session_snapshot()
        if str(market_session.get("status") or "closed") not in {"closed", "lunch_break"}:
            with self._lock:
                self._tick_archive_backfill_last_run_ms = now_ms
                self._tick_archive_backfill_last_error = ""
                self._tick_archive_backfill_next_run_ms = now_ms + max(self.config.tick_archive_backfill_poll_sec, 10) * 1000
            return
        trade_date_text = self._trade_date_text()
        start_time, end_time = self._trade_window(trade_date_text)
        with self._lock:
            symbols = list(self._tick_source_snapshot.symbols[: self.config.tick_keepalive_max_symbols])
        if not symbols:
            with self._lock:
                self._tick_archive_backfill_last_run_ms = now_ms
                self._tick_archive_backfill_last_error = ""
                self._tick_archive_backfill_next_run_ms = now_ms + max(self.config.tick_archive_backfill_poll_sec, 10) * 1000
            return
        self._emit_runtime_log(
            "tick_archive_backfill_started",
            trade_date=trade_date_text,
            symbol_count=len(symbols),
            symbols=symbols,
            start_time=start_time,
            end_time=end_time,
        )
        retry_ms = max(self.config.tick_archive_backfill_retry_sec, 30) * 1000
        any_written = False
        cycle_status: Dict[str, Dict[str, object]] = {}
        cycle_stats = {
            "replayed": 0,
            "already_replayed": 0,
            "cooldown": 0,
            "backfill_failed": 0,
            "empty": 0,
            "count_failed": 0,
        }
        total_symbols = len(symbols)
        with self._lock:
            self._tick_keepalive_pause_reason = "tick_archive_backfill"
        try:
            for symbol_index, symbol in enumerate(symbols, start=1):
                attempt_key = f"{trade_date_text}:{symbol}"
                with self._lock:
                    if attempt_key in self._tick_archive_backfill_completed_keys:
                        cycle_status[symbol] = {
                            "trade_date": trade_date_text,
                            "status": "already_replayed",
                            "count": 0,
                        }
                        cycle_stats["already_replayed"] += 1
                        self._emit_runtime_log(
                            "tick_archive_backfill_symbol_skipped",
                            symbol=symbol,
                            symbol_index=symbol_index,
                            total_symbols=total_symbols,
                            trade_date=trade_date_text,
                            status="already_replayed",
                        )
                        continue
                with self._lock:
                    retry_at_ms = self._tick_archive_backfill_retry_at_ms.get(attempt_key, 0)
                if retry_at_ms > now_ms:
                    cycle_status[symbol] = {
                        "trade_date": trade_date_text,
                        "status": "cooldown",
                        "retry_at_ms": retry_at_ms,
                        "count": 0,
                    }
                    cycle_stats["cooldown"] += 1
                    self._emit_runtime_log(
                        "tick_archive_backfill_symbol_skipped",
                        symbol=symbol,
                        symbol_index=symbol_index,
                        total_symbols=total_symbols,
                        trade_date=trade_date_text,
                        status="cooldown",
                        retry_at_ms=retry_at_ms,
                    )
                    continue
                try:
                    existing_count = self._tick_archive.count_ticks(symbol, trade_date_text)
                except Exception as exc:
                    with self._lock:
                        self._tick_archive_backfill_retry_at_ms[attempt_key] = now_ms + retry_ms
                    cycle_status[symbol] = {
                        "trade_date": trade_date_text,
                        "status": "count_failed",
                        "detail": str(exc),
                        "retry_at_ms": now_ms + retry_ms,
                    }
                    cycle_stats["count_failed"] += 1
                    self._emit_runtime_log(
                        "tick_archive_backfill_symbol_failed",
                        symbol=symbol,
                        symbol_index=symbol_index,
                        total_symbols=total_symbols,
                        trade_date=trade_date_text,
                        status="count_failed",
                        detail=str(exc),
                        retry_at_ms=now_ms + retry_ms,
                    )
                    continue
                if existing_count > 0:
                    cycle_status[symbol] = {
                        "trade_date": trade_date_text,
                        "status": "replaying_full_day",
                        "existing_count": existing_count,
                    }
                self._emit_runtime_log(
                    "tick_archive_backfill_symbol_started",
                    symbol=symbol,
                    symbol_index=symbol_index,
                    total_symbols=total_symbols,
                    trade_date=trade_date_text,
                    existing_count=existing_count,
                    start_time=start_time,
                    end_time=end_time,
                )
                try:
                    records = self.provider.backfill_ticks(symbol, start_time=start_time, end_time=end_time)
                except Exception as exc:
                    with self._lock:
                        self._tick_archive_backfill_retry_at_ms[attempt_key] = now_ms + retry_ms
                    cycle_status[symbol] = {
                        "trade_date": trade_date_text,
                        "status": "backfill_failed",
                        "detail": str(exc),
                        "retry_at_ms": now_ms + retry_ms,
                    }
                    cycle_stats["backfill_failed"] += 1
                    self._emit_runtime_log(
                        "tick_archive_backfill_failed",
                        symbol=symbol,
                        symbol_index=symbol_index,
                        total_symbols=total_symbols,
                        trade_date=trade_date_text,
                        detail=str(exc),
                    )
                    continue
                if not records:
                    with self._lock:
                        self._tick_archive_backfill_retry_at_ms[attempt_key] = now_ms + retry_ms
                    cycle_status[symbol] = {
                        "trade_date": trade_date_text,
                        "status": "empty",
                        "count": 0,
                        "retry_at_ms": now_ms + retry_ms,
                    }
                    cycle_stats["empty"] += 1
                    self._emit_runtime_log(
                        "tick_archive_backfill_empty",
                        symbol=symbol,
                        symbol_index=symbol_index,
                        total_symbols=total_symbols,
                        trade_date=trade_date_text,
                    )
                    continue
                for record in records:
                    self._tick_archive.append_event(
                        symbol,
                        MarketEvent(topic=SubscriptionTopic(kind="tick", symbol=symbol), symbol=symbol, payload=record).to_dict(),
                    )
                with self._lock:
                    self._tick_archive_backfill_retry_at_ms.pop(attempt_key, None)
                    self._tick_archive_backfill_completed_keys.add(attempt_key)
                cycle_status[symbol] = {
                    "trade_date": trade_date_text,
                    "status": "replayed",
                    "existing_count": existing_count,
                    "count": len(records),
                }
                cycle_stats["replayed"] += 1
                any_written = True
                self._emit_runtime_log(
                    "tick_archive_backfill_enqueued",
                    symbol=symbol,
                    symbol_index=symbol_index,
                    total_symbols=total_symbols,
                    trade_date=trade_date_text,
                    existing_count=existing_count,
                    record_count=len(records),
                )
        finally:
            with self._lock:
                self._tick_keepalive_pause_reason = ""
                self._sync_tick_keepalives_locked(int(time.time() * 1000))
        with self._lock:
            self._tick_archive_backfill_last_run_ms = now_ms
            self._tick_archive_backfill_next_run_ms = now_ms + max(self.config.tick_archive_backfill_poll_sec, 10) * 1000
            self._tick_archive_backfill_status = cycle_status
            self._tick_archive_backfill_last_error = ""
            if any_written:
                self._tick_archive_backfill_last_success_ms = now_ms
        self._emit_runtime_log(
            "tick_archive_backfill_completed",
            trade_date=trade_date_text,
            symbol_count=len(symbols),
            stats=cycle_stats,
        )

    def _bar_backfill_loop(self) -> None:
        interval_sec = max(self.config.bar_backfill_poll_sec, 10)
        while self._running:
            now_ms = int(time.time() * 1000)
            try:
                self._run_bar_backfill_cycle(now_ms)
            except Exception as exc:
                with self._lock:
                    self._bar_backfill_last_error = str(exc)
                    self._bar_backfill_last_run_ms = now_ms
                    self._bar_backfill_next_run_ms = now_ms + interval_sec * 1000
                self._emit_runtime_log("bar_backfill_cycle_failed", detail=str(exc))
            time.sleep(interval_sec)

    def run_bar_backfill_plan_once(
        self,
        stage: str,
        *,
        trade_date_text: str = "",
        symbols: Tuple[str, ...] = (),
        now_ms: int = 0,
        dry_run: bool = False,
    ) -> Dict[str, object]:
        clean_stage = str(stage or "").strip().lower()
        if clean_stage not in {"lunch_repair", "close_finalize", "nightly_recent_days", "weekend_gap_scan"}:
            raise ValueError(f"unsupported bar backfill stage: {stage}")
        if not self._bar_archive.enabled() or not self.config.bar_backfill_enabled:
            raise RuntimeError("bar backfill is disabled")
        effective_trade_date = str(trade_date_text or "").strip() or self._trade_date_text()
        with self._lock:
            effective_symbols = symbols or tuple(self._tick_source_snapshot.symbols[: self.config.tick_keepalive_max_symbols])
        current_now_ms = now_ms or int(time.time() * 1000)
        return self._execute_bar_backfill_stage(
            clean_stage,
            trade_date_text=effective_trade_date,
            now_ms=current_now_ms,
            now_local=datetime.now().astimezone(),
            symbols=tuple(str(symbol or "").strip().upper() for symbol in effective_symbols if str(symbol or "").strip()),
            dry_run=dry_run,
        )

    def _run_bar_backfill_cycle(self, now_ms: int) -> None:
        if not self._bar_archive.enabled() or not self.config.bar_backfill_enabled:
            return
        market_session = self._get_market_session_snapshot()
        now_local = datetime.now().astimezone()
        stage = self._resolve_bar_backfill_stage(market_session, now_local)
        interval_sec = max(self.config.bar_backfill_poll_sec, 10)
        if not stage:
            with self._lock:
                self._bar_backfill_last_run_ms = now_ms
                self._bar_backfill_last_error = ""
                self._bar_backfill_next_run_ms = now_ms + interval_sec * 1000
            return
        trade_date_text = self._trade_date_text()
        with self._lock:
            symbols = tuple(self._tick_source_snapshot.symbols[: self.config.tick_keepalive_max_symbols])
        result = self._execute_bar_backfill_stage(
            stage,
            trade_date_text=trade_date_text,
            now_ms=now_ms,
            now_local=now_local,
            symbols=symbols,
            dry_run=False,
        )
        if not bool(result.get("tasks")):
            with self._lock:
                self._bar_backfill_last_run_ms = now_ms
                self._bar_backfill_last_error = ""
                self._bar_backfill_next_run_ms = now_ms + interval_sec * 1000
            return

    def _execute_bar_backfill_stage(
        self,
        stage: str,
        *,
        trade_date_text: str,
        now_ms: int,
        now_local: datetime,
        symbols: Tuple[str, ...],
        dry_run: bool,
    ) -> Dict[str, object]:
        interval_sec = max(self.config.bar_backfill_poll_sec, 10)
        tasks = self._resolve_bar_backfill_tasks(stage, trade_date_text=trade_date_text, symbols=symbols)
        if not tasks:
            return {
                "stage": stage,
                "trade_date": trade_date_text,
                "task_count": 0,
                "symbol_count": 0,
                "tasks": [],
                "dry_run": dry_run,
            }
        task_count = len(tasks)
        symbol_count = sum(len(task.symbols) for task in tasks)
        self._emit_runtime_log(
            "bar_backfill_scheduler_started",
            stage=stage,
            task_count=task_count,
            symbol_count=symbol_count,
            trade_dates=[task.trade_date_text for task in tasks],
            overall_symbol_index=0,
            overall_symbol_count=symbol_count,
            overall_progress_pct=self._progress_percent(0, symbol_count),
            progress=self._bar_backfill_progress_text(
                task_index=0,
                task_count=task_count,
                symbol_index=0,
                total_symbols=symbol_count if symbol_count > 0 else 1,
                overall_symbol_index=0,
                overall_symbol_count=symbol_count,
            ),
        )
        task_payloads = [
            {
                "trade_date": task.trade_date_text,
                "stage": task.stage,
                "start_time": task.start_time,
                "end_time": task.end_time,
                "symbols": list(task.symbols),
            }
            for task in tasks
        ]
        if dry_run:
            return {
                "stage": stage,
                "trade_date": trade_date_text,
                "task_count": task_count,
                "symbol_count": symbol_count,
                "tasks": task_payloads,
                "dry_run": True,
            }
        retry_ms = max(self.config.bar_backfill_retry_sec, 30) * 1000
        cycle_status: Dict[str, Dict[str, object]] = {}
        any_written = False
        processed_symbols = 0
        written_symbol_count = 0
        written_rows_total = 0
        complete_count = 0
        partial_count = 0
        empty_count = 0
        failed_count = 0
        skipped_count = 0
        for task_index, task in enumerate(tasks, start=1):
            window_start = self._parse_compact_datetime(task.start_time)
            window_end = self._parse_compact_datetime(task.end_time)
            expected_bars = self._expected_bar_count(task.start_time, task.end_time)
            total_symbols = len(task.symbols)
            effective_workers = min(
                total_symbols,
                max(self.config.bar_backfill_symbol_workers, 1),
                max(self.config.bar_backfill_provider_max_concurrency, 1),
            )
            self._emit_runtime_log(
                "bar_backfill_scheduler_task_started",
                stage=task.stage,
                trade_date=task.trade_date_text,
                task_index=task_index,
                task_count=task_count,
                symbol_count=total_symbols,
                worker_count=effective_workers,
                start_time=task.start_time,
                end_time=task.end_time,
                overall_symbol_index=processed_symbols,
                overall_symbol_count=symbol_count,
                overall_progress_pct=self._progress_percent(processed_symbols, symbol_count),
                progress=self._bar_backfill_progress_text(
                    task_index=task_index,
                    task_count=task_count,
                    symbol_index=0,
                    total_symbols=total_symbols if total_symbols > 0 else 1,
                    overall_symbol_index=processed_symbols,
                    overall_symbol_count=symbol_count,
                ),
            )
            pending_symbol_tasks: List[BarBackfillSymbolTask] = []
            for symbol_index, symbol in enumerate(task.symbols, start=1):
                attempt_key = f"{task.trade_date_text}:{task.stage}:{symbol}"
                status_key = self._bar_status_key(task.trade_date_text, task.stage, symbol)
                with self._lock:
                    if attempt_key in self._bar_backfill_completed_keys:
                        cycle_status[status_key] = {
                            "trade_date": task.trade_date_text,
                            "stage": task.stage,
                            "status": "already_repaired",
                        }
                        processed_symbols += 1
                        skipped_count += 1
                        self._emit_runtime_log(
                            "bar_backfill_scheduler_symbol_completed",
                            symbol=symbol,
                            trade_date=task.trade_date_text,
                            stage=task.stage,
                            task_index=task_index,
                            task_count=task_count,
                            symbol_index=symbol_index,
                            total_symbols=total_symbols,
                            overall_symbol_index=processed_symbols,
                            overall_symbol_count=symbol_count,
                            task_progress_pct=self._progress_percent(symbol_index, total_symbols),
                            overall_progress_pct=self._progress_percent(processed_symbols, symbol_count),
                            status="already_repaired",
                            expected_bars=expected_bars,
                            actual_bars=expected_bars,
                            written_rows=0,
                            progress=self._bar_backfill_progress_text(
                                task_index=task_index,
                                task_count=task_count,
                                symbol_index=symbol_index,
                                total_symbols=total_symbols,
                                overall_symbol_index=processed_symbols,
                                overall_symbol_count=symbol_count,
                            ),
                        )
                        continue
                    retry_at_ms = self._bar_backfill_retry_at_ms.get(attempt_key, 0)
                    attempt_count = self._bar_backfill_attempt_counts.get(attempt_key, 0) + 1
                    self._bar_backfill_attempt_counts[attempt_key] = attempt_count
                if retry_at_ms > now_ms:
                    cycle_status[status_key] = {
                        "trade_date": task.trade_date_text,
                        "stage": task.stage,
                        "status": "cooldown",
                        "retry_at_ms": retry_at_ms,
                    }
                    processed_symbols += 1
                    skipped_count += 1
                    self._emit_runtime_log(
                        "bar_backfill_scheduler_symbol_completed",
                        symbol=symbol,
                        trade_date=task.trade_date_text,
                        stage=task.stage,
                        task_index=task_index,
                        task_count=task_count,
                        symbol_index=symbol_index,
                        total_symbols=total_symbols,
                        overall_symbol_index=processed_symbols,
                        overall_symbol_count=symbol_count,
                        task_progress_pct=self._progress_percent(symbol_index, total_symbols),
                        overall_progress_pct=self._progress_percent(processed_symbols, symbol_count),
                        status="cooldown",
                        expected_bars=expected_bars,
                        actual_bars=0,
                        written_rows=0,
                        retry_at_ms=retry_at_ms,
                        progress=self._bar_backfill_progress_text(
                            task_index=task_index,
                            task_count=task_count,
                            symbol_index=symbol_index,
                            total_symbols=total_symbols,
                            overall_symbol_index=processed_symbols,
                            overall_symbol_count=symbol_count,
                        ),
                    )
                    continue
                job_key = f"{task.trade_date_text}:{task.stage}:{symbol}:serve"
                raw_context = {
                    "task_index": task_index,
                    "task_count": task_count,
                    "symbol_index": symbol_index,
                    "total_symbols": total_symbols,
                }
                self._record_bar_backfill_job(
                    job_key=job_key,
                    trade_date_text=task.trade_date_text,
                    symbol=symbol,
                    stage=task.stage,
                    status="running",
                    attempt_count=attempt_count,
                    expected_bars=expected_bars,
                    actual_bars=0,
                    written_rows=0,
                    window_start=window_start,
                    window_end=window_end,
                    started_at=now_local,
                    finished_at=None,
                    detail="",
                    last_error="",
                    raw_json=raw_context,
                )
                self._emit_runtime_log(
                    "bar_backfill_scheduler_symbol_started",
                    symbol=symbol,
                    symbol_index=symbol_index,
                    total_symbols=total_symbols,
                    trade_date=task.trade_date_text,
                    stage=task.stage,
                    task_index=task_index,
                    task_count=task_count,
                    start_time=task.start_time,
                    end_time=task.end_time,
                )
                pending_symbol_tasks.append(
                    BarBackfillSymbolTask(
                        symbol=symbol,
                        trade_date_text=task.trade_date_text,
                        stage=task.stage,
                        start_time=task.start_time,
                        end_time=task.end_time,
                        expected_bars=expected_bars,
                        task_index=task_index,
                        task_count=task_count,
                        symbol_index=symbol_index,
                        total_symbols=total_symbols,
                        attempt_key=attempt_key,
                        status_key=status_key,
                        job_key=job_key,
                        attempt_count=attempt_count,
                        window_start=window_start,
                        window_end=window_end,
                        raw_context=raw_context,
                        progress_text="",
                    )
                )
            future_results = []
            if effective_workers <= 1:
                for symbol_task in pending_symbol_tasks:
                    try:
                        result = self._run_bar_backfill_symbol_task(symbol_task)
                    except Exception as exc:
                        result = BarBackfillSymbolResult(
                            status="failed",
                            expected_bars=symbol_task.expected_bars,
                            actual_bars=0,
                            written_rows=0,
                            detail=str(exc),
                        )
                    future_results.append((symbol_task, result))
            else:
                with ThreadPoolExecutor(max_workers=effective_workers) as executor:
                    future_map = {
                        executor.submit(self._run_bar_backfill_symbol_task, symbol_task): symbol_task
                        for symbol_task in pending_symbol_tasks
                    }
                    for future in as_completed(future_map):
                        symbol_task = future_map[future]
                        try:
                            result = future.result()
                        except Exception as exc:
                            result = BarBackfillSymbolResult(
                                status="failed",
                                expected_bars=symbol_task.expected_bars,
                                actual_bars=0,
                                written_rows=0,
                                detail=str(exc),
                            )
                        future_results.append((symbol_task, result))
            for symbol_task, result in future_results:
                if result.status == "failed":
                    with self._lock:
                        self._bar_backfill_retry_at_ms[symbol_task.attempt_key] = now_ms + retry_ms
                    cycle_status[symbol_task.status_key] = {
                        "trade_date": symbol_task.trade_date_text,
                        "stage": symbol_task.stage,
                        "status": "failed",
                        "detail": result.detail,
                        "retry_at_ms": now_ms + retry_ms,
                    }
                    self._record_bar_backfill_job(
                        job_key=symbol_task.job_key,
                        trade_date_text=symbol_task.trade_date_text,
                        symbol=symbol_task.symbol,
                        stage=symbol_task.stage,
                        status="failed",
                        attempt_count=symbol_task.attempt_count,
                        expected_bars=symbol_task.expected_bars,
                        actual_bars=result.actual_bars,
                        written_rows=0,
                        window_start=symbol_task.window_start,
                        window_end=symbol_task.window_end,
                        started_at=now_local,
                        finished_at=datetime.now().astimezone(),
                        detail="run_bar_backfill_failed",
                        last_error=result.detail,
                        raw_json=symbol_task.raw_context,
                    )
                    processed_symbols += 1
                    failed_count += 1
                    self._emit_runtime_log(
                        "bar_backfill_scheduler_symbol_completed",
                        symbol=symbol_task.symbol,
                        trade_date=symbol_task.trade_date_text,
                        stage=symbol_task.stage,
                        task_index=symbol_task.task_index,
                        task_count=symbol_task.task_count,
                        symbol_index=symbol_task.symbol_index,
                        total_symbols=symbol_task.total_symbols,
                        overall_symbol_index=processed_symbols,
                        overall_symbol_count=symbol_count,
                        task_progress_pct=self._progress_percent(symbol_task.symbol_index, symbol_task.total_symbols),
                        overall_progress_pct=self._progress_percent(processed_symbols, symbol_count),
                        status="failed",
                        expected_bars=symbol_task.expected_bars,
                        actual_bars=result.actual_bars,
                        written_rows=0,
                        retry_at_ms=now_ms + retry_ms,
                        detail=result.detail,
                        progress=self._bar_backfill_progress_text(
                            task_index=symbol_task.task_index,
                            task_count=symbol_task.task_count,
                            symbol_index=symbol_task.symbol_index,
                            total_symbols=symbol_task.total_symbols,
                            overall_symbol_index=processed_symbols,
                            overall_symbol_count=symbol_count,
                        ),
                    )
                    continue
                self._record_bar_coverage(
                    trade_date_text=symbol_task.trade_date_text,
                    symbol=symbol_task.symbol,
                    stage=symbol_task.stage,
                    expected_bars=symbol_task.expected_bars,
                    actual_bars=result.actual_bars,
                    window_start=symbol_task.window_start,
                    window_end=symbol_task.window_end,
                    first_bar_time=result.first_bar_time,
                    last_bar_time=result.last_bar_time,
                    status=result.status,
                    note=result.note,
                    raw_json={**symbol_task.raw_context, "written_rows": result.written_rows},
                )
                self._record_bar_backfill_job(
                    job_key=symbol_task.job_key,
                    trade_date_text=symbol_task.trade_date_text,
                    symbol=symbol_task.symbol,
                    stage=symbol_task.stage,
                    status=result.status,
                    attempt_count=symbol_task.attempt_count,
                    expected_bars=symbol_task.expected_bars,
                    actual_bars=result.actual_bars,
                    written_rows=result.written_rows,
                    window_start=symbol_task.window_start,
                    window_end=symbol_task.window_end,
                    started_at=now_local,
                    finished_at=datetime.now().astimezone(),
                    detail=result.note,
                    last_error="",
                    raw_json=symbol_task.raw_context,
                )
                if result.status == "complete":
                    with self._lock:
                        self._bar_backfill_retry_at_ms.pop(symbol_task.attempt_key, None)
                        self._bar_backfill_completed_keys.add(symbol_task.attempt_key)
                else:
                    with self._lock:
                        self._bar_backfill_retry_at_ms[symbol_task.attempt_key] = now_ms + retry_ms
                cycle_status[symbol_task.status_key] = {
                    "trade_date": symbol_task.trade_date_text,
                    "stage": symbol_task.stage,
                    "status": result.status,
                    "expected_bars": symbol_task.expected_bars,
                    "actual_bars": result.actual_bars,
                    "written_rows": result.written_rows,
                }
                processed_symbols += 1
                written_rows_total += result.written_rows
                if result.written_rows > 0:
                    written_symbol_count += 1
                if result.status == "complete":
                    complete_count += 1
                elif result.status == "partial":
                    partial_count += 1
                else:
                    empty_count += 1
                self._emit_runtime_log(
                    "bar_backfill_scheduler_symbol_completed",
                    symbol=symbol_task.symbol,
                    trade_date=symbol_task.trade_date_text,
                    stage=symbol_task.stage,
                    task_index=symbol_task.task_index,
                    task_count=symbol_task.task_count,
                    symbol_index=symbol_task.symbol_index,
                    total_symbols=symbol_task.total_symbols,
                    overall_symbol_index=processed_symbols,
                    overall_symbol_count=symbol_count,
                    task_progress_pct=self._progress_percent(symbol_task.symbol_index, symbol_task.total_symbols),
                    overall_progress_pct=self._progress_percent(processed_symbols, symbol_count),
                    status=result.status,
                    expected_bars=symbol_task.expected_bars,
                    actual_bars=result.actual_bars,
                    written_rows=result.written_rows,
                    progress=self._bar_backfill_progress_text(
                        task_index=symbol_task.task_index,
                        task_count=symbol_task.task_count,
                        symbol_index=symbol_task.symbol_index,
                        total_symbols=symbol_task.total_symbols,
                        overall_symbol_index=processed_symbols,
                        overall_symbol_count=symbol_count,
                    ),
                )
                any_written = any_written or result.written_rows > 0
        with self._lock:
            self._bar_backfill_last_run_ms = now_ms
            self._bar_backfill_next_run_ms = now_ms + interval_sec * 1000
            self._bar_backfill_status = cycle_status
            self._bar_backfill_last_error = ""
            if any_written:
                self._bar_backfill_last_success_ms = now_ms
        self._emit_runtime_log(
            "bar_backfill_scheduler_completed",
            stage=stage,
            task_count=task_count,
            symbol_count=symbol_count,
            processed_symbols=processed_symbols,
            complete_count=complete_count,
            partial_count=partial_count,
            empty_count=empty_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            written_symbol_count=written_symbol_count,
            written_rows_total=written_rows_total,
            overall_progress_pct=self._progress_percent(processed_symbols, symbol_count),
        )
        return {
            "stage": stage,
            "trade_date": trade_date_text,
            "task_count": task_count,
            "symbol_count": symbol_count,
            "tasks": task_payloads,
            "symbols": dict(cycle_status),
            "dry_run": False,
        }

    def _record_bar_backfill_job(
        self,
        *,
        job_key: str,
        trade_date_text: str,
        symbol: str,
        stage: str,
        status: str,
        attempt_count: int,
        expected_bars: int,
        actual_bars: int,
        written_rows: int,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        started_at: Optional[datetime],
        finished_at: Optional[datetime],
        detail: str,
        last_error: str,
        raw_json: Dict[str, object],
    ) -> None:
        try:
            self._bar_backfill_state.upsert_job(
                job_key=job_key,
                trade_date=datetime.strptime(trade_date_text, "%Y-%m-%d").date(),
                symbol=symbol,
                period="1m",
                stage=stage,
                scheduler_source="serve",
                status=status,
                attempt_count=attempt_count,
                expected_bars=expected_bars,
                actual_bars=actual_bars,
                written_rows=written_rows,
                window_start=window_start,
                window_end=window_end,
                started_at=started_at,
                finished_at=finished_at,
                detail=detail,
                last_error=last_error,
                raw_json=raw_json,
            )
        except Exception as exc:
            self._emit_runtime_log(
                "bar_backfill_job_write_failed",
                symbol=symbol,
                stage=stage,
                detail=str(exc),
            )

    def _record_bar_coverage(
        self,
        *,
        trade_date_text: str,
        symbol: str,
        stage: str,
        expected_bars: int,
        actual_bars: int,
        window_start: Optional[datetime],
        window_end: Optional[datetime],
        first_bar_time: Optional[datetime],
        last_bar_time: Optional[datetime],
        status: str,
        note: str,
        raw_json: Dict[str, object],
    ) -> None:
        try:
            self._bar_backfill_state.upsert_coverage(
                trade_date=datetime.strptime(trade_date_text, "%Y-%m-%d").date(),
                symbol=symbol,
                period="1m",
                stage=stage,
                window_start=window_start,
                window_end=window_end,
                expected_bars=expected_bars,
                actual_bars=actual_bars,
                first_bar_time=first_bar_time,
                last_bar_time=last_bar_time,
                status=status,
                source=self.provider.name(),
                note=note,
                raw_json=raw_json,
            )
        except Exception as exc:
            self._emit_runtime_log(
                "bar_backfill_coverage_write_failed",
                symbol=symbol,
                stage=stage,
                detail=str(exc),
            )

    def _bar_status_key(self, trade_date_text: str, stage: str, symbol: str) -> str:
        if trade_date_text == self._trade_date_text() and stage in {"lunch_repair", "close_finalize"}:
            return symbol
        return f"{trade_date_text}:{symbol}"

    def _expected_bar_count(self, start_time: str, end_time: str) -> int:
        return (
            self._session_overlap_minutes(start_time, end_time, "093000", "113000")
            + self._session_overlap_minutes(start_time, end_time, "130000", "150000")
        )

    def _session_overlap_minutes(self, start_time: str, end_time: str, session_start: str, session_end: str) -> int:
        start_minute = self._compact_to_minutes(start_time)
        end_minute = self._compact_to_minutes(end_time)
        session_start_minute = self._compact_to_minutes(start_time[:8] + session_start)
        session_end_minute = self._compact_to_minutes(start_time[:8] + session_end)
        return max(0, min(end_minute, session_end_minute) - max(start_minute, session_start_minute))

    def _compact_to_minutes(self, compact_text: str) -> int:
        parsed = self._parse_compact_datetime(compact_text)
        if parsed is None:
            return 0
        return parsed.hour * 60 + parsed.minute

    def _parse_compact_datetime(self, compact_text: str) -> Optional[datetime]:
        text = str(compact_text or "").strip()
        if len(text) != 14 or not text.isdigit():
            return None
        parsed = datetime.strptime(text, "%Y%m%d%H%M%S")
        return parsed.astimezone() if parsed.tzinfo else parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)

    def _tick_keepalive_loop(self) -> None:
        next_source_refresh = 0.0
        while self._running:
            now = time.time()
            if self._tick_source is not None and now >= next_source_refresh:
                self._refresh_tick_source()
                next_source_refresh = now + max(self.config.tick_keepalive_source_refresh_sec, 5)
            with self._lock:
                self._sync_tick_keepalives_locked(int(now * 1000))
                self._sync_bar_keepalives_locked()
            time.sleep(max(self.config.tick_keepalive_poll_sec, 1))

    def _refresh_tick_source(self) -> None:
        if self._tick_source is None:
            return
        try:
            snapshot = self._tick_source.load()
            with self._lock:
                self._tick_source_snapshot = snapshot
                self._tick_source_last_error = ""
                for symbol in snapshot.symbols[: self.config.tick_keepalive_max_symbols]:
                    state = self._tick_keepalives.get(symbol)
                    if state is None:
                        state = TickKeepaliveState(symbol=symbol)
                        self._tick_keepalives[symbol] = state
                    state.pinned = True
                source_symbols = set(snapshot.symbols)
                for symbol, state in self._tick_keepalives.items():
                    if symbol not in source_symbols:
                        state.pinned = False
        except Exception as exc:
            with self._lock:
                self._tick_source_last_error = str(exc)

    def _bootstrap_tick_keepalives(self) -> None:
        with self._lock:
            symbols = list(self._tick_source_snapshot.symbols[: self.config.tick_keepalive_max_symbols])
        self._emit_runtime_log(
            "tick_keepalive_bootstrap_started",
            symbol_count=len(symbols),
            symbols=symbols,
        )
        with self._lock:
            self._sync_tick_keepalives_locked(int(time.time() * 1000))
            active_count = sum(1 for state in self._tick_keepalives.values() if state.handle)
        self._emit_runtime_log(
            "tick_keepalive_bootstrap_completed",
            symbol_count=len(symbols),
            active_count=active_count,
        )

    def _bootstrap_bar_keepalives(self) -> None:
        if not self._bar_archive.enabled():
            return
        with self._lock:
            symbols = list(self._tick_source_snapshot.symbols[: self.config.tick_keepalive_max_symbols])
            self._sync_bar_keepalives_locked()
            active_count = sum(1 for state in self._bar_keepalives.values() if state.handle)
        self._emit_runtime_log(
            "bar_keepalive_bootstrap_completed",
            symbol_count=len(symbols),
            active_count=active_count,
        )

    def _should_archive_tick_symbol(self, symbol: str) -> bool:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol or not self._tick_archive.enabled():
            return False
        with self._lock:
            return clean_symbol in set(self._tick_source_snapshot.symbols)

    def _should_archive_bar_symbol(self, symbol: str) -> bool:
        clean_symbol = str(symbol or "").strip().upper()
        if not clean_symbol or not self._bar_archive.enabled():
            return False
        with self._lock:
            return clean_symbol in set(self._tick_source_snapshot.symbols)

    def _archive_bar_event(self, symbol: str, period: str, payload: Dict[str, object]) -> None:
        if not self._should_archive_bar_symbol(symbol):
            return
        try:
            self._bar_archive.upsert_bars(symbol, period, [payload], source=self.provider.name())
        except Exception as exc:
            self._emit_runtime_log(
                "bar_archive_write_failed",
                symbol=symbol,
                period=period,
                detail=str(exc),
            )

    def _sync_tick_keepalives_locked(self, now_ms: int) -> None:
        expiry_ms = max(self.config.tick_keepalive_ttl_sec, 30) * 1000
        stale_symbols: List[str] = []
        pause_new_subscriptions = bool(self._tick_keepalive_pause_reason)
        for symbol, state in self._tick_keepalives.items():
            manual_alive = state.manual_touch_ms > 0 and now_ms - state.manual_touch_ms <= expiry_ms
            desired = state.pinned or manual_alive
            has_stream = self._has_active_tick_stream_locked(symbol)
            if not desired:
                if state.handle:
                    try:
                        self.provider.unsubscribe(state.handle)
                        self._emit_runtime_log(
                            "tick_keepalive_unsubscribed",
                            symbol=symbol,
                            handle=state.handle,
                            reason="expired",
                        )
                    except Exception:
                        pass
                stale_symbols.append(symbol)
                continue
            if has_stream:
                if state.handle:
                    try:
                        self.provider.unsubscribe(state.handle)
                        self._emit_runtime_log(
                            "tick_keepalive_unsubscribed",
                            symbol=symbol,
                            handle=state.handle,
                            reason="stream_attached",
                        )
                    except Exception:
                        pass
                    state.handle = ""
                continue
            if state.handle:
                continue
            if pause_new_subscriptions:
                continue
            try:
                state.handle = self.provider.subscribe(SubscriptionTopic(kind="tick", symbol=symbol), self._on_provider_event)
                state.last_error = ""
                self._emit_runtime_log(
                    "tick_keepalive_subscribed",
                    symbol=symbol,
                    handle=state.handle,
                    pinned=state.pinned,
                    manual_touch_ms=state.manual_touch_ms,
                )
            except Exception as exc:
                state.last_error = str(exc)
                self._emit_runtime_log("tick_keepalive_subscribe_failed", symbol=symbol, detail=state.last_error)
        for symbol in stale_symbols:
            self._tick_keepalives.pop(symbol, None)

    def _has_active_tick_stream_locked(self, symbol: str) -> bool:
        state = self._provider_states.get(SubscriptionTopic(kind="tick", symbol=symbol).key())
        return bool(state and state.watcher_count > 0 and state.handle)

    def _sync_bar_keepalives_locked(self) -> None:
        desired_symbols = set()
        if self._bar_archive.enabled():
            desired_symbols = set(self._tick_source_snapshot.symbols[: self.config.tick_keepalive_max_symbols])
        for symbol in desired_symbols:
            self._bar_keepalives.setdefault(symbol, BarKeepaliveState(symbol=symbol))
        stale_symbols: List[str] = []
        for symbol, state in self._bar_keepalives.items():
            if symbol not in desired_symbols:
                if state.handle:
                    try:
                        self.provider.unsubscribe(state.handle)
                        self._emit_runtime_log(
                            "bar_keepalive_unsubscribed",
                            symbol=symbol,
                            handle=state.handle,
                            reason="source_removed",
                        )
                    except Exception:
                        pass
                stale_symbols.append(symbol)
                continue
            if self._has_active_bar_stream_locked(symbol):
                if state.handle:
                    try:
                        self.provider.unsubscribe(state.handle)
                        self._emit_runtime_log(
                            "bar_keepalive_unsubscribed",
                            symbol=symbol,
                            handle=state.handle,
                            reason="stream_attached",
                        )
                    except Exception:
                        pass
                    state.handle = ""
                continue
            if state.handle:
                continue
            try:
                state.handle = self.provider.subscribe(
                    SubscriptionTopic(kind="bar", symbol=symbol, period="1m"),
                    self._on_provider_event,
                )
                state.last_error = ""
                self._emit_runtime_log(
                    "bar_keepalive_subscribed",
                    symbol=symbol,
                    handle=state.handle,
                    period="1m",
                )
            except Exception as exc:
                state.last_error = str(exc)
                self._emit_runtime_log("bar_keepalive_subscribe_failed", symbol=symbol, detail=state.last_error)
        for symbol in stale_symbols:
            self._bar_keepalives.pop(symbol, None)

    def _has_active_bar_stream_locked(self, symbol: str) -> bool:
        state = self._provider_states.get(SubscriptionTopic(kind="bar", symbol=symbol, period="1m").key())
        return bool(state and state.watcher_count > 0 and state.handle)

    def _l2_poll_loop(self) -> None:
        while self._running:
            time.sleep(max(self.config.l2_poll_interval_ms, 100) / 1000.0)
            with self._lock:
                states = [
                    state
                    for state in self._provider_states.values()
                    if state.topic.kind in {"l2_quote", "l2_order", "l2_transaction"}
                    and state.watcher_count > 0
                    and not state.handle
                ]
            for state in states:
                self._poll_l2_state(state)

    def _poll_l2_state(self, state: ProviderSubscriptionState) -> None:
        topic = state.topic
        try:
            current_day = time.strftime("%Y%m%d", time.localtime())
            if state.l2_day and state.l2_day != current_day:
                state.l2_cursor = None
            state.l2_day = current_day
            if topic.kind == "l2_quote":
                records = self.provider.get_l2_quote(topic.symbol, 32)
            elif topic.kind == "l2_order":
                records = self.provider.get_l2_order(topic.symbol, 32)
            else:
                records = self.provider.get_l2_transaction(topic.symbol, 32)
            state.last_poll_ms = int(time.time() * 1000)
            cursor = unique_records_key(records)
            if not records or cursor == state.l2_cursor:
                return
            state.l2_cursor = cursor
            for record in records[-4:]:
                self._on_provider_event(topic, topic.symbol, record)
        except Exception as exc:
            state.last_error = str(exc)
